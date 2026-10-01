# Johnathan 'Qasparr' (Κασπάρρ) Monroe, Keeper of the Secret Treasure
# All Rights Reserved, Without Prejudice.  CashApp $axoneme
"""benchmarks -- the gate weighed against itself.

How fast does the Anchorage weigh? This suite times the primitives
(weigh_claim per kind) and full workings (admit over N claims) so the
API can report, chart, and compare the gate's own performance over
time. Pure stdlib; deterministic workloads, wall-clock timing.

A benchmark run records, per benchmark: operations, total seconds,
operations/second, and milliseconds per operation.
"""

from __future__ import annotations

import time

from .anchorage import Claim, admit, weigh_claim


def _quote_claim(i: int) -> Claim:
    text = f"benchmark claim number {i}"
    return Claim(text=text, kind="quote",
                 proof={"source": f"a source containing {text} verbatim"})


def _number_claim(i: int) -> Claim:
    return Claim(text=f"{i}+{i}", kind="number",
                 proof={"recompute": (lambda n=i: n + n), "expected": 2 * i})


def _citation_claim() -> Claim:
    return Claim(text="319 U.S. 105 (1943)", kind="citation")


def _assertion_claim(i: int) -> Claim:
    return Claim(text=f"unproven assertion {i}", kind="assertion")


def _mixed_working(n: int) -> list[Claim]:
    makers = (_quote_claim, _number_claim,
              lambda i: _citation_claim(), _assertion_claim)
    return [makers[i % 4](i) for i in range(n)]


def _time(fn, iterations: int) -> dict:
    start = time.perf_counter()
    for _ in range(iterations):
        fn()
    total = time.perf_counter() - start
    total = max(total, 1e-9)
    return {
        "operations": iterations,
        "total_seconds": round(total, 6),
        "ops_per_second": round(iterations / total, 1),
        "ms_per_op": round(total / iterations * 1000, 4),
    }


def run(iterations: int = 1000) -> dict[str, dict]:
    """Run the full suite. ``iterations`` scales the per-claim benches;
    the admit benches use fixed working sizes (10/50/100 claims)."""
    quote = _quote_claim(1)
    number = _number_claim(1)
    citation = _citation_claim()
    assertion = _assertion_claim(1)
    w10 = _mixed_working(10)
    w50 = _mixed_working(50)
    w100 = _mixed_working(100)
    return {
        "weigh_quote": _time(lambda: weigh_claim(quote), iterations),
        "weigh_number": _time(lambda: weigh_claim(number), iterations),
        "weigh_citation": _time(lambda: weigh_claim(citation), iterations),
        "weigh_assertion": _time(lambda: weigh_claim(assertion), iterations),
        "admit_10_claims": _time(lambda: admit(w10),
                                 max(iterations // 10, 10)),
        "admit_50_claims": _time(lambda: admit(w50),
                                 max(iterations // 50, 5)),
        "admit_100_claims": _time(lambda: admit(w100),
                                  max(iterations // 100, 3)),
    }


def compare(previous: dict[str, dict],
            current: dict[str, dict]) -> dict[str, dict]:
    """Per-benchmark delta of ops/sec, current vs previous run."""
    out = {}
    for name, cur in current.items():
        prev = previous.get(name)
        if not prev:
            out[name] = {"delta_pct": None, "note": "no previous run"}
            continue
        p, c = prev["ops_per_second"], cur["ops_per_second"]
        delta = ((c - p) / p * 100) if p else 0.0
        out[name] = {
            "previous_ops": p,
            "current_ops": c,
            "delta_pct": round(delta, 2),
        }
    return out
