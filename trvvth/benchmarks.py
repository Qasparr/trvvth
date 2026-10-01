# Johnathan 'Qasparr' (Κασπάρρ) Monroe, Keeper of the Secret Treasure
# All Rights Reserved, Without Prejudice.  CashApp $axoneme
"""benchmarks -- the gate weighed against itself.

    "For which of you, intending to build a tower, sitteth not down
     first, and counteth the cost, whether he have sufficient to
     finish it?"
    -- Luke 14:28

Hypothesis
----------
A gate that will be asked to weigh ten thousand claims should know,
before the asking, what each weighing costs. Benchmarking is the
counting of the cost: not vanity metrics, but the measured price of
the primitives -- one claim weighed, one working admitted -- so the
operator can sit down first and reckon whether the tower stands.

Method
------
Deterministic workloads, wall-clock timing, pure stdlib. The suite
times two scales of the gate's labor:

* *Primitives* -- ``weigh_claim`` against one claim of each kind
  (quote, number, citation, assertion), repeated ``iterations``
  times. This isolates the cost of each weighing rule: the verbatim
  search, the recomputation, the citation patterns, the honest
  refusal.
* *Workings* -- ``admit`` over mixed 10/50/100-claim workings. The
  working sizes grow while the repetition count shrinks
  (``iterations // size``, floored), because a 100-claim working
  costs roughly 100 weighings and the suite should finish before
  the operator's coffee cools.

``_time`` takes the wall clock with ``perf_counter`` -- the
monotonic clock, immune to the system clock being adjusted
mid-measurement -- and reports operations, total seconds,
operations/second, and milliseconds per operation. Wall-clock
rather than CPU time is deliberate: the gate's cost as experienced
is what the operator pays, thread scheduling and all.

Observation
-----------
The workloads are fixed functions of the loop index (``_quote_claim``,
``_number_claim``, and friends build the same-shaped claims every
run), so run-to-run comparison measures the gate and the machine,
not the dice. ``compare`` reduces two runs to per-benchmark delta
percentages of ops/sec -- positive means the current run is faster,
and a missing previous benchmark is reported as "no previous run,"
never as zero.

Result
------
The API stores every run in the ledger and charts throughput across
runs. The gate's speed becomes part of its record -- counted,
witnessed, and comparable -- which is the whole of the tower
parables' counsel: count first, then build.

Thelemic parallel
------------------
"Every number is infinite; there is no difference." -- Liber AL,
I:4. The benchmark's numbers are not infinite -- they are finite,
measured, and humbly wall-clock -- which is precisely why they are
useful: the infinite needs no counting, but the tower does.
"""

from __future__ import annotations

import time

from .anchorage import Claim, admit, weigh_claim


def _quote_claim(i: int) -> Claim:
    """A quote-claim whose source contains the text verbatim.

    The ``i`` parameter varies the text so the suite weighs many
    distinct claims rather than one cached shape -- the verbatim
    search (``text in source``) must actually search each time.
    """
    text = f"benchmark claim number {i}"
    return Claim(text=text, kind="quote",
                 proof={"source": f"a source containing {text} verbatim"})


def _number_claim(i: int) -> Claim:
    """A number-claim with a true recomputation.

    The lambda closes over ``i`` *by value* (``lambda n=i: n + n``)
    -- the classic late-binding guard, so each claim recomputes its
    own sum rather than all thousand recomputing the last one.
    """
    return Claim(text=f"{i}+{i}", kind="number",
                 proof={"recompute": (lambda n=i: n + n), "expected": 2 * i})


def _citation_claim() -> Claim:
    """A format-plausible citation: exercises the pattern list."""
    return Claim(text="319 U.S. 105 (1943)", kind="citation")


def _assertion_claim(i: int) -> Claim:
    """A bare assertion: the gate's cheapest honest answer."""
    return Claim(text=f"unproven assertion {i}", kind="assertion")


def _mixed_working(n: int) -> list[Claim]:
    """A working of ``n`` claims, cycling evenly through the four kinds.

    The rotation (quote, number, citation, assertion) keeps every
    working representative of real traffic rather than a pathological
    monoculture -- the admit benchmarks measure the gate as it will
    actually labor, not as it labors in the best case.
    """
    makers = (_quote_claim, _number_claim,
              lambda i: _citation_claim(), _assertion_claim)
    return [makers[i % 4](i) for i in range(n)]


def _time(fn, iterations: int) -> dict:
    """Time ``fn`` over ``iterations`` calls; return the accounting.

    ``perf_counter`` is the monotonic wall clock -- immune to NTP
    adjustments and daylight-saving changes mid-run, which is what
    you want when you are counting a cost. ``total`` is floored at
    one nanosecond so a zero-duration measurement (possible on coarse
    clocks for trivial functions) yields an enormous ops/sec rather
    than a ZeroDivisionError -- the honest report of "too fast to
    measure" is a very large number, not a crash.
    """
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
    """Run the full suite; return per-benchmark accountings.

    ``iterations`` scales the four primitive benches directly. The
    admit benches use fixed working sizes (10/50/100 claims) with
    repetition counts scaled *down* by size (``iterations // size``,
    floored at a minimum) -- because the cost of a working grows
    with its claims, holding total labor roughly constant keeps the
    suite's runtime predictable. The returned dict maps benchmark
    names to their ``_time`` accountings.
    """
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
    """Per-benchmark delta of ops/sec, current run vs previous run.

    The delta is ``(current - previous) / previous * 100`` -- positive
    means faster. A benchmark absent from the previous run reports
    ``delta_pct: None`` with the note "no previous run" rather than
    inventing a baseline of zero, which would manufacture a
    meaningless infinite improvement. The comparison judges the
    judging, as the axis demands.
    """
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
