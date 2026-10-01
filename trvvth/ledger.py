# Johnathan 'Qasparr' (Κασπάρρ) Monroe, Keeper of the Secret Treasure
# All Rights Reserved, Without Prejudice.  CashApp $axoneme
"""ledger -- the gate's own books, kept in sqlite (stdlib, cross-platform).

    "One witness shall not rise up against a man for any iniquity...
     at the mouth of two witnesses, or at the mouth of three
     witnesses, shall the matter be established."
    -- Deuteronomy 19:15

Hypothesis
----------
A gate that weighs claims should keep its own record the way the Law
keeps one: every matter established by witnesses, written down, and
retrievable. Three ledgers in one file serve the three surfaces that
need memory:

* *admissions* -- every working the gate weighed: the verdict
  tallies, whether it was admitted, whether Oz x Duty held, and the
  full payload as JSON (the mouth of the witnesses, verbatim).
* *requests* -- every HTTP request the API served: method, path,
  status, duration in milliseconds. The app watching itself -- the
  witness that the server was awake and how long it labored.
* *benchmark_runs* -- every benchmark run against the gate: its
  parameters and per-benchmark results as JSON, so today's gate can
  be weighed against yesterday's.

Method
------
sqlite, from the standard library: a single file, no server, no
driver to install, identical behavior on every platform Python
reaches. The schema is created idempotently (``CREATE TABLE IF NOT
EXISTS``), so opening an existing ledger never disturbs it -- the
book opens where it left off.

The subtle analysis -- worth stating plainly because it bites every
first implementation -- is threading. Uvicorn runs synchronous
endpoints in a threadpool, while the connection is opened once in
the application's lifespan; a sqlite connection created in one
thread refuses, by default, to be used in another. Two measures
answer it, and both are needed:

1. ``check_same_thread=False`` at connect time, which lifts the
   thread-affinity guard; and
2. a single module-level ``threading.Lock`` (``_LOCK``) held by
   every writer, which restores the safety the guard provided --
   sqlite's own locking serializes the file, but the Python-level
   lock keeps two threads from interleaving statements on the one
   shared connection object.

Reads take no lock: sqlite permits concurrent readers, and a torn
read here would only ever produce a chart missing its newest bar,
never a wrong admission.

Observation
-----------
``record_admission`` returns the row id, which the API hands back as
``ledger_id`` -- every admission carries its own receipt. The
aggregation queries (``admission_summary``, ``verdict_counts``,
``daily_workings``, ``request_stats``) are plain SQL over indexed
timestamp columns; the per-kind tally (``claims_by_kind``) walks the
stored payloads, trading a scan for schema simplicity -- the ledger
stores what the gate saw, not a pre-digested shadow of it.

Result
------
The gate remembers. Reports, analytics, and benchmark history are
not separate systems bolted on; they are readings of the one book.
Move the file (``TRVVTH_LEDGER``) and the memory moves with it.

Law
---
A ledger is kept the way evidence is kept: complete, contemporaneous,
and retrievable -- cf. the authentication principle of Fed. R. Evid.
901(a), already cited in trvvth.anchorage. The ledger does not make a
verdict true; it records that the verdict was rendered, by what
gate, and when. Cited for education only; this module creates no
legal effect.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time

# One lock guarding the single connection. Uvicorn runs sync endpoints
# in a threadpool while the lifespan opens the connection once in the
# main thread; without this lock two threads could interleave writes
# on the shared connection object. With it, every write is atomic
# from the application's point of view -- the ledger never records
# half a working. (See the module docstring for the full analysis.)
_LOCK = threading.Lock()

# The whole schema, applied idempotently on every connect. Three
# tables, two timestamp indexes. ``payload`` and ``results`` are JSON
# text: the ledger stores the working as the gate saw it, verbatim,
# rather than a normalized shadow that could drift from the truth.
SCHEMA = """
CREATE TABLE IF NOT EXISTS admissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    admitted INTEGER NOT NULL,
    n_claims INTEGER NOT NULL,
    n_trvvth INTEGER NOT NULL,
    n_unresolved INTEGER NOT NULL,
    n_rhetoric INTEGER NOT NULL,
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
    """Open (or create) the ledger file and ensure the schema.

    ``check_same_thread=False`` is deliberate and documented: the
    connection is opened in the lifespan thread and used from
    uvicorn's worker threads. Thread safety is restored by ``_LOCK``
    around every writer -- the flag alone would be a hazard, the lock
    alone would deadlock against sqlite's own guard; together they
    are the correct construction. See the module docstring.

    Schema evolution is handled here, not in the callers: ledgers
    written before the RHETORIC verdict existed have no n_rhetoric
    column, and the gate must read old books without rewriting them.
    After the base schema is ensured, ``_migrate`` adds any missing
    columns idempotently -- PRAGMA first, ALTER only when absent --
    so a ledger from v0.2.1 opens cleanly under v0.2.2 and its old
    rows simply tally zero rhetoric, which is exactly what they
    contain.
    """
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    """Idempotent schema migration for verdicts added after v0.2.1.

    Hypothesis: a ledger written by an older gate must remain
    readable -- the books are a witness statement, and a witness
    statement is not rewritten when the court learns a new word.

    Method: inspect the live table with PRAGMA table_info; ALTER
    TABLE ... ADD COLUMN only for columns the table lacks. New
    columns are NOT NULL DEFAULT 0 so old rows tally honestly.

    Observation: on a v0.2.1 ledger, n_rhetoric is absent and gets
    added; on a v0.2.2 ledger it is present and nothing happens.

    Result: connect() is safe to call against any ledger this
    project has ever written, and every verdict-listing query can
    name every verdict without fear of a missing column.
    """
    cols = {row[1] for row in
            conn.execute("PRAGMA table_info(admissions)").fetchall()}
    # Column additions, in doctrine order: (name, definition).
    # Each is independent; a future verdict adds one tuple here.
    additions = (
        ("n_rhetoric", "INTEGER NOT NULL DEFAULT 0"),
    )
    for name, definition in additions:
        if name not in cols:
            conn.execute(f"ALTER TABLE admissions ADD COLUMN {name} "
                         f"{definition}")
    conn.commit()


def record_admission(conn: sqlite3.Connection, *, admitted: bool,
                     n_claims: int, verdicts: dict[str, int],
                     balance_holds: bool, payload: dict) -> int:
    """Write one weighed working to the admissions ledger.

    The verdict tallies are stored as columns (they are what the
    reports aggregate), while the full payload -- the claims as
    submitted, the stamp, the admission -- is stored as JSON text,
    verbatim. The returned row id is the working's receipt; the API
    returns it as ``ledger_id`` so any admission can be cited back
    to its exact row.
    """
    with _LOCK:
        cur = conn.execute(
            "INSERT INTO admissions (ts, admitted, n_claims, n_trvvth,"
            " n_unresolved, n_rhetoric, n_falsehood, balance_holds, payload)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (time.time(), int(admitted), n_claims,
             verdicts.get("TRVVTH", 0), verdicts.get("UNRESOLVED", 0),
             verdicts.get("RHETORIC", 0), verdicts.get("FALSEHOOD", 0),
             int(balance_holds),
             json.dumps(payload)),
        )
        conn.commit()
        return cur.lastrowid


def record_request(conn: sqlite3.Connection, *, method: str, path: str,
                   status: int, duration_ms: float) -> None:
    """Write one served HTTP request to the analytics ledger.

    Called by the API's middleware after every response. The
    ``/docs`` route is excluded by the caller -- the operator's own
    browsing should not pollute the traffic it came to read.
    """
    with _LOCK:
        conn.execute(
            "INSERT INTO requests (ts, method, path, status, duration_ms)"
            " VALUES (?, ?, ?, ?, ?)",
            (time.time(), method, path, status, duration_ms),
        )
        conn.commit()


def record_benchmark(conn: sqlite3.Connection, *, iterations: int,
                     results: dict) -> int:
    """Write one benchmark run. Returns its id for later comparison."""
    with _LOCK:
        cur = conn.execute(
            "INSERT INTO benchmark_runs (ts, iterations, results)"
            " VALUES (?, ?, ?)",
            (time.time(), iterations, json.dumps(results)),
        )
        conn.commit()
        return cur.lastrowid


def admission_summary(conn: sqlite3.Connection) -> dict:
    """Tally the whole admissions book in one pass.

    Returns workings weighed, workings admitted, the admission rate,
    total claims, the verdict tallies, and how many workings held
    their Oz x Duty balance. Division by zero is guarded: an empty
    ledger reports a rate of 0.0, not an error -- no workings, no
    rate, honestly stated.
    """
    row = conn.execute(
        "SELECT COUNT(*), SUM(admitted), SUM(n_claims), SUM(n_trvvth),"
        " SUM(n_unresolved), SUM(n_rhetoric), SUM(n_falsehood),"
        " SUM(balance_holds)"
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
            "RHETORIC": row[5] or 0,
            "FALSEHOOD": row[6] or 0,
        },
        "balance_holds": row[7] or 0,
    }


def ledger_page(conn: sqlite3.Connection, limit: int = 50,
                offset: int = 0, admitted: bool | None = None) -> list[dict]:
    """Page the admissions ledger, newest first.

    ``admitted`` is a tri-state filter: True/False narrows to that
    outcome, None returns both. Payloads are deliberately excluded
    from the page -- the ledger's index names the workings; the full
    witness statement is one more query away, not freighted onto
    every listing.
    """
    q = ("SELECT id, ts, admitted, n_claims, n_trvvth, n_unresolved,"
         " n_rhetoric, n_falsehood, balance_holds FROM admissions")
    args: list = []
    if admitted is not None:
        q += " WHERE admitted = ?"
        args.append(int(admitted))
    q += " ORDER BY id DESC LIMIT ? OFFSET ?"
    args += [limit, offset]
    return [dict(zip(
        ("id", "ts", "admitted", "n_claims", "n_trvvth",
         "n_unresolved", "n_rhetoric", "n_falsehood", "balance_holds"), r))
        for r in conn.execute(q, args).fetchall()]


def verdict_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """The alethic account, summed across every working on the books."""
    row = conn.execute(
        "SELECT SUM(n_trvvth), SUM(n_unresolved), SUM(n_rhetoric),"
        " SUM(n_falsehood)"
        " FROM admissions").fetchone()
    return {"TRVVTH": row[0] or 0, "UNRESOLVED": row[1] or 0,
            "RHETORIC": row[2] or 0, "FALSEHOOD": row[3] or 0}


def claims_by_kind(conn: sqlite3.Connection) -> dict[str, int]:
    """Count claims by kind, by walking the stored payloads.

    This is a scan rather than an indexed aggregate, by design: the
    ledger stores what the gate saw (the payload JSON), not a
    pre-digested shadow of it, so new analyses can always be derived
    from the primary record. Corrupt payloads are skipped, never
    fatal -- one bad row must not sink the report.
    """
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
    """Workings and admissions per calendar day, oldest first.

    Dates are computed in SQL (``date(ts, 'unixepoch')``) so the
    bucketing is the database's, not the reporter's -- one
    definition of "day," shared by every chart drawn from it.
    """
    rows = conn.execute(
        "SELECT date(ts, 'unixepoch') AS day, COUNT(*), SUM(admitted)"
        " FROM admissions WHERE ts > strftime('%s','now', ?)"
        " GROUP BY day ORDER BY day",
        (f"-{days} days",)).fetchall()
    return [{"day": r[0], "workings": r[1], "admitted": r[2] or 0}
            for r in rows]


def request_stats(conn: sqlite3.Connection) -> dict:
    """The app's self-knowledge: traffic, latency, and error rate.

    Returns the total request count, the fraction that ended in
    server errors (status >= 500 -- the app grading its own
    failures), mean and maximum latency in milliseconds, and the
    twenty hottest paths with their hit counts and mean latencies.
    An empty analytics book reports zeros, not errors.
    """
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
    """Mean latency in 5-minute buckets, oldest first, for charting.

    Bucketing by ``CAST(ts / 300 AS INTEGER)`` keeps the series
    bounded no matter how long the server has run: sixty points
    describe the last five hours, and older history compresses
    gracefully instead of drowning the chart.
    """
    rows = conn.execute(
        "SELECT ts, AVG(duration_ms) FROM requests"
        " GROUP BY CAST(ts / 300 AS INTEGER)"
        " ORDER BY ts DESC LIMIT ?", (points,)).fetchall()
    return [{"ts": r[0], "avg_ms": r[1] or 0.0} for r in reversed(rows)]


def benchmark_history(conn: sqlite3.Connection,
                      limit: int = 20) -> list[dict]:
    """Past benchmark runs, newest first, results decoded from JSON."""
    rows = conn.execute(
        "SELECT id, ts, iterations, results FROM benchmark_runs"
        " ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [{"id": r[0], "ts": r[1], "iterations": r[2],
             "results": json.loads(r[3])} for r in rows]


def benchmark_run(conn: sqlite3.Connection, run_id: int) -> dict | None:
    """One benchmark run by id, or None if no such run exists."""
    r = conn.execute(
        "SELECT id, ts, iterations, results FROM benchmark_runs"
        " WHERE id = ?", (run_id,)).fetchone()
    if r is None:
        return None
    return {"id": r[0], "ts": r[1], "iterations": r[2],
            "results": json.loads(r[3])}
