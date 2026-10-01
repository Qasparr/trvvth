# Johnathan 'Qasparr' (Κασπάρρ) Monroe, Keeper of the Secret Treasure
# All Rights Reserved, Without Prejudice.  CashApp $axoneme
"""ledger -- the gate's own books, kept in sqlite (stdlib, cross-platform).

Three ledgers, one file:
* admissions -- every working the gate weighed: verdict tallies, whether
  it was admitted, whether Oz x Duty held, the full payload as JSON.
* requests -- every HTTP request the API served: method, path, status,
  duration in milliseconds. The app watches itself.
* benchmark_runs -- every benchmark run against the gate: parameters
  and per-benchmark results as JSON.

All writers take an explicit sqlite3 connection; the API owns one
connection per process (sqlite is fine with that under uvicorn's
default single-process server).
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time

# One lock guarding the single connection; uvicorn runs sync
# endpoints in a threadpool, so the connection must also allow
# cross-thread use.
_LOCK = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS admissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    admitted INTEGER NOT NULL,
    n_claims INTEGER NOT NULL,
    n_trvvth INTEGER NOT NULL,
    n_unresolved INTEGER NOT NULL,
    n_falsehood INTEGER NOT NULL,
    balance_holds INTEGER NOT NULL,
    payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    method TEXT NOT NULL,
    path TEXT NOT NULL,
    status INTEGER NOT NULL,
    duration_ms REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS benchmark_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    iterations INTEGER NOT NULL,
    results TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_admissions_ts ON admissions(ts);
CREATE INDEX IF NOT EXISTS idx_requests_ts ON requests(ts);
"""


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.executescript(SCHEMA)
    return conn


def record_admission(conn: sqlite3.Connection, *, admitted: bool,
                     n_claims: int, verdicts: dict[str, int],
                     balance_holds: bool, payload: dict) -> int:
    with _LOCK:
        cur = conn.execute(
            "INSERT INTO admissions (ts, admitted, n_claims, n_trvvth,"
            " n_unresolved, n_falsehood, balance_holds, payload)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (time.time(), int(admitted), n_claims,
             verdicts.get("TRVVTH", 0), verdicts.get("UNRESOLVED", 0),
             verdicts.get("FALSEHOOD", 0), int(balance_holds),
             json.dumps(payload)),
        )
        conn.commit()
        return cur.lastrowid


def record_request(conn: sqlite3.Connection, *, method: str, path: str,
                   status: int, duration_ms: float) -> None:
    with _LOCK:
        conn.execute(
            "INSERT INTO requests (ts, method, path, status, duration_ms)"
            " VALUES (?, ?, ?, ?, ?)",
            (time.time(), method, path, status, duration_ms),
        )
        conn.commit()


def record_benchmark(conn: sqlite3.Connection, *, iterations: int,
                     results: dict) -> int:
    with _LOCK:
        cur = conn.execute(
            "INSERT INTO benchmark_runs (ts, iterations, results)"
            " VALUES (?, ?, ?)",
            (time.time(), iterations, json.dumps(results)),
        )
        conn.commit()
        return cur.lastrowid


def admission_summary(conn: sqlite3.Connection) -> dict:
    row = conn.execute(
        "SELECT COUNT(*), SUM(admitted), SUM(n_claims), SUM(n_trvvth),"
        " SUM(n_unresolved), SUM(n_falsehood), SUM(balance_holds)"
        " FROM admissions").fetchone()
    workings = row[0] or 0
    return {
        "workings": workings,
        "admitted": row[1] or 0,
        "admission_rate": (row[1] or 0) / workings if workings else 0.0,
        "claims": row[2] or 0,
        "verdicts": {
            "TRVVTH": row[3] or 0,
            "UNRESOLVED": row[4] or 0,
            "FALSEHOOD": row[5] or 0,
        },
        "balance_holds": row[6] or 0,
    }


def ledger_page(conn: sqlite3.Connection, limit: int = 50,
                offset: int = 0, admitted: bool | None = None) -> list[dict]:
    q = ("SELECT id, ts, admitted, n_claims, n_trvvth, n_unresolved,"
         " n_falsehood, balance_holds FROM admissions")
    args: list = []
    if admitted is not None:
        q += " WHERE admitted = ?"
        args.append(int(admitted))
    q += " ORDER BY id DESC LIMIT ? OFFSET ?"
    args += [limit, offset]
    return [dict(zip(
        ("id", "ts", "admitted", "n_claims", "n_trvvth",
         "n_unresolved", "n_falsehood", "balance_holds"), r))
        for r in conn.execute(q, args).fetchall()]


def verdict_counts(conn: sqlite3.Connection) -> dict[str, int]:
    row = conn.execute(
        "SELECT SUM(n_trvvth), SUM(n_unresolved), SUM(n_falsehood)"
        " FROM admissions").fetchone()
    return {"TRVVTH": row[0] or 0, "UNRESOLVED": row[1] or 0,
            "FALSEHOOD": row[2] or 0}


def claims_by_kind(conn: sqlite3.Connection) -> dict[str, int]:
    counts: dict[str, int] = {}
    for (payload,) in conn.execute("SELECT payload FROM admissions").fetchall():
        try:
            for claim in json.loads(payload).get("claims", []):
                kind = claim.get("kind", "unknown")
                counts[kind] = counts.get(kind, 0) + 1
        except (ValueError, AttributeError):
            continue
    return counts


def daily_workings(conn: sqlite3.Connection, days: int = 30) -> list[dict]:
    rows = conn.execute(
        "SELECT date(ts, 'unixepoch') AS day, COUNT(*), SUM(admitted)"
        " FROM admissions WHERE ts > strftime('%s','now', ?)"
        " GROUP BY day ORDER BY day",
        (f"-{days} days",)).fetchall()
    return [{"day": r[0], "workings": r[1], "admitted": r[2] or 0}
            for r in rows]


def request_stats(conn: sqlite3.Connection) -> dict:
    total = conn.execute("SELECT COUNT(*) FROM requests").fetchone()[0] or 0
    by_path = conn.execute(
        "SELECT path, COUNT(*), AVG(duration_ms) FROM requests"
        " GROUP BY path ORDER BY COUNT(*) DESC LIMIT 20").fetchall()
    lat = conn.execute(
        "SELECT AVG(duration_ms), MAX(duration_ms) FROM requests").fetchone()
    errors = conn.execute(
        "SELECT COUNT(*) FROM requests WHERE status >= 500").fetchone()[0] or 0
    return {
        "total_requests": total,
        "error_rate": errors / total if total else 0.0,
        "avg_latency_ms": lat[0] or 0.0,
        "max_latency_ms": lat[1] or 0.0,
        "by_path": [{"path": r[0], "hits": r[1], "avg_ms": r[2] or 0.0}
                    for r in by_path],
    }


def latency_series(conn: sqlite3.Connection, points: int = 60) -> list[dict]:
    rows = conn.execute(
        "SELECT ts, AVG(duration_ms) FROM requests"
        " GROUP BY CAST(ts / 300 AS INTEGER)"
        " ORDER BY ts DESC LIMIT ?", (points,)).fetchall()
    return [{"ts": r[0], "avg_ms": r[1] or 0.0} for r in reversed(rows)]


def benchmark_history(conn: sqlite3.Connection,
                      limit: int = 20) -> list[dict]:
    rows = conn.execute(
        "SELECT id, ts, iterations, results FROM benchmark_runs"
        " ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [{"id": r[0], "ts": r[1], "iterations": r[2],
             "results": json.loads(r[3])} for r in rows]


def benchmark_run(conn: sqlite3.Connection, run_id: int) -> dict | None:
    r = conn.execute(
        "SELECT id, ts, iterations, results FROM benchmark_runs"
        " WHERE id = ?", (run_id,)).fetchone()
    if r is None:
        return None
    return {"id": r[0], "ts": r[1], "iterations": r[2],
            "results": json.loads(r[3])}
