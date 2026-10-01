# Johnathan 'Qasparr' (Κασπάρρ) Monroe, Keeper of the Secret Treasure
# All Rights Reserved, Without Prejudice.  CashApp $axoneme
"""api -- the TRVVTH gate as a cross-platform HTTP API.

    "Prove all things; hold fast that which is good."
    -- 1 Thessalonians 5:21

    "Invoke me under my stars! Love is the law, love under will."
    -- Liber AL, I:57

Hypothesis
----------
The zero-trust gate should not require the Python interpreter at the
caller's elbow. Claims arrive over HTTP from any platform; verdicts
return over HTTP; nothing about the trust model changes in transit.
The gate's wiring -- whose duties count, whose clock stamps -- is
still injected, never assumed, but now the injection happens through
environment and process boundaries rather than function arguments.

Method
------
FastAPI + uvicorn: pure Python, no compiled extensions, identical on
Linux, macOS, and Windows -- the cross-platform requirement is met
by refusing to depend on anything platform-specific. The module is
organized as four surfaces over one gate:

* *The gate itself* (``/admit``, ``/weigh``, ``/kinds``,
  ``/verdicts``, ``/cardinal-rules``): the Anchorage, reachable.
  Number-claims cross the wire as arithmetic expressions evaluated
  by ``trvvth.safeval`` -- the ``recompute`` callable cannot survive
  JSON, so the expression is the wire form and the safe evaluator is
  its guardian.
* *Diagnostics* (``/diagnostics/*``): health, a known-answer
  self-test run through the *live* gate (not a mock of it), a wiring
  report naming what the process was injected with, and the
  benchmark suite with run history.
* *Reports* (``/reports/*``): the admission ledger, its summary,
  and SVG charts drawn from it.
* *Analytics* (``/analytics/*``): the app watching itself --
  request counts, latency, error rates, and their charts.

Persistence is one sqlite file (``trvvth.ledger``): admissions,
request analytics, and benchmark runs are three tables in one book.
The middleware records every request's method, path, status, and
duration -- but analytics must never break the gate, so the
recording is wrapped in a try/except that swallows everything: a
failed witness is better than a fallen gate.

The Thelemic verse stands over the wiring section deliberately:
"Love is the law, love under will." The injected duty resolver is
law -- the strict canonical check -- and it operates *under will*,
the operator's will, expressed through ``TRVVTH_DUTY_RESOLVER``. Law
without will is tyranny; will without law is weather. The gate
holds both, in that order.

Observation
-----------
``POST /admit`` returns the full ``AdmitOut`` -- per-claim verdicts,
the Oz x Duty balance (including which rights stand unbalanced and
which named duties failed canonical resolution), the stamp, and the
``ledger_id`` receipt. The OpenAPI schema at ``/docs``, ReDoc at
``/redoc``, and the hand-written operator's guide at ``/guide``
document the same surface three ways: machine-readable,
human-browsable, and narrative.

Result
------
The gate any agent can use, now usable by any agent that speaks
HTTP -- which is to say, any of them. The trust model did not move:
no claim enters on authority, including the API's own.

Law
---
The API admits workings, not exhibits; every citation herein is
educational. Cf. Fed. R. Evid. 901(a) (authentication as condition
precedent), cited at length in trvvth.anchorage -- the principle
travels with the gate across the wire unchanged.
"""

from __future__ import annotations

import importlib
import os
import time
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel, Field

from . import __version__
from .alethic import FALSEHOOD, RHETORIC, TRVVTH, UNRESOLVED
from .anchorage import (
    KINDS,
    Claim,
    admit,
    cardinal_rules,
    weigh_claim,
)
from . import benchmarks as bench
from . import charts as svg
from . import ledger as db
from .safeval import evaluate as safe_evaluate


# ---------------------------------------------------------------- models
# The wire shapes. Pydantic validates the JSON before the gate ever
# sees it: malformed claims are refused at the door with a 422, which
# is the API's own small act of zero-trust -- the gate weighs claims,
# but it should never have to weigh garbage.

class ClaimIn(BaseModel):
    """One claim as it arrives over the wire.

    ``proof`` is the interesting field: for quotes it carries
    ``{"source": "..."}``; for numbers it carries ``{"expression":
    "17+76", "expected": 93}`` -- the expression is evaluated by
    ``trvvth.safeval`` at admission time (see ``_claim_from``). The
    ``recompute`` callable of the Python API has no wire form, by
    necessity: functions do not survive JSON. ``right``/``duty`` are
    the Oz x Duty pairing; a right without its duty unbalances the
    working exactly as in the Python gate.
    """
    text: str = Field(..., description="The claim as stated.")
    kind: str = Field("assertion",
                      description="quote | number | citation | assertion")
    proof: dict[str, Any] = Field(
        default_factory=dict,
        description='quote -> {"source": "..."}; number -> {"expression":'
                    ' "17+76", "expected": 93}; citation/assertion -> {}')
    right: Optional[str] = Field(None, description="Right asserted, if any.")
    duty: Optional[str] = Field(None,
                                description="Duty paired with the right.")


class AdmitIn(BaseModel):
    """A working offered to the gate: one or more claims, plus stamp options."""
    claims: list[ClaimIn] = Field(..., min_length=1)
    stamp: Optional[str] = Field(None, description="Override the UTC stamp.")
    sun_in_anchorage: bool = False
    moon_in_anchorage: bool = False


class AssessmentOut(BaseModel):
    """One weighed claim, as the API reports it."""
    kind: str
    text: str
    verdict: str
    note: str


class AdmitOut(BaseModel):
    """The weighed working: verdicts, balance, stamp, and receipt.

    ``ledger_id`` is the row in the admissions ledger -- the
    working's receipt, citable back to the exact record.
    ``unbalanced_rights`` names the rights that arrived without
    duties; ``unresolved_duties`` names the rights whose named duty
    failed the canonical resolver (empty when no resolver is
    wired, or when all resolve).
    """
    admitted: bool
    stamp: str
    anchorage: str
    assessments: list[AssessmentOut]
    balance_holds: bool
    unbalanced_rights: list[str]
    unresolved_duties: list[str]
    ledger_id: int


# ------------------------------------------------------- wiring & lifespan
# "Love is the law, love under will." -- Liber AL, I:57.
# The duty resolver is law (the strict canonical check); the
# environment variable is will (the operator's choice). The gate
# enforces the pairing either way -- with a resolver wired, named
# duties must resolve; without one, a named duty is taken at face
# value and only the pairing itself is enforced. Both are honest;
# the wiring report says which is in force.

def _load_duty_resolver():
    """Load the strict duty registry from ``TRVVTH_DUTY_RESOLVER``.

    The variable names ``module:attribute`` -- a module importable
    from the server process and the attribute holding the resolver
    callable. Absent variable: open pairing (no resolver). Malformed
    value: the error is captured, not raised at import -- a server
    that refuses to start over a misconfigured optional is a gate
    that locked its own operator out. The wiring endpoint reports
    the error honestly.
    """
    dotted = os.environ.get("TRVVTH_DUTY_RESOLVER")
    if not dotted:
        return None
    mod_name, _, attr = dotted.partition(":")
    if not attr:
        raise RuntimeError(
            "TRVVTH_DUTY_RESOLVER must be 'module:attribute'")
    return getattr(importlib.import_module(mod_name), attr)


DUTY_RESOLVER = None
DUTY_RESOLVER_ERROR: str | None = None
try:
    DUTY_RESOLVER = _load_duty_resolver()
except Exception as exc:  # noqa: BLE001 -- reported via /diagnostics/wiring
    DUTY_RESOLVER_ERROR = repr(exc)

CONN = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Open the ledger for the process's lifetime; close it on shutdown.

    The ledger path comes from ``TRVVTH_LEDGER`` (default
    ``./trvvth-ledger.db``) -- moving the file moves the gate's
    memory. The path is stashed on ``app.state`` so the wiring
    report can name it.
    """
    global CONN
    path = os.environ.get("TRVVTH_LEDGER", "trvvth-ledger.db")
    CONN = db.connect(path)
    app.state.ledger_path = path
    yield
    CONN.close()


app = FastAPI(
    title="TRVVTH -- the Zero-Trust Anchorage",
    description=("The gate any agent can use: claims in, verdicts out,"
                 " no trust assumed. Diagnostics, reports, analytics,"
                 " and benchmarks included."),
    version=__version__,
    lifespan=lifespan,
)


@app.middleware("http")
async def _analytics(request: Request, call_next):
    """Time every request and witness it to the analytics ledger.

    The duration is measured around the whole downstream handling
    and recorded with method, path, and status -- this is the app
    watching itself, the witness of its own labor. Two deliberate
    choices:

    1. ``/docs`` is excluded: the operator's own browsing of the
       schema should not pollute the traffic it came to read.
    2. The recording is wrapped in try/except and swallows
       everything: analytics must never break the gate. A failed
       witness is a gap in the record; a crashed admission is a
       failure of the work. The hierarchy is absolute.

    The measured milliseconds are also returned as the
    ``X-TRVVTH-ms`` header -- the server stating its own cost
    honestly, on every response.
    """
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    if CONN is not None and not request.url.path.startswith("/docs"):
        try:
            db.record_request(CONN, method=request.method,
                              path=request.url.path,
                              status=response.status_code,
                              duration_ms=duration_ms)
        except Exception:  # noqa: BLE001 -- analytics must never break the gate
            pass
    response.headers["X-TRVVTH-ms"] = f"{duration_ms:.2f}"
    return response


def _claim_from(data: ClaimIn) -> Claim:
    """Translate a wire claim into the gate's ``Claim``.

    The translation is where the wire form meets the Python form:
    a number-claim carrying ``proof.expression`` gets a
    ``recompute`` closure over ``trvvth.safeval.evaluate`` -- the
    closure binds the expression *by value* (default argument), so
    each claim carries its own expression even when translated in a
    loop. The ``expected`` value passes through untouched for the
    gate to compare against. All other kinds pass their proof
    through verbatim: the wire adds nothing and takes nothing.
    """
    proof = dict(data.proof)
    if data.kind == "number" and "expression" in proof:
        expression = proof.pop("expression")
        expected = proof.get("expected")
        proof["recompute"] = (lambda e=expression: safe_evaluate(e))
        proof["expected"] = expected
    return Claim(text=data.text, kind=data.kind, proof=proof,
                 right=data.right, duty=data.duty)


def _admit_out(working, ledger_id: int) -> AdmitOut:
    """Render an ``AnchoredWorking`` as the API's ``AdmitOut``.

    The anchorage sentence names which lights stood in the
    Anchorage (Sun/Moon flags) or states plainly that the moment
    fell outside it -- the stamp authenticates *when*, never
    *whether*, and the sentence says so either way.
    """
    anchor = []
    if working.sun_in_anchorage:
        anchor.append("Sun")
    if working.moon_in_anchorage:
        anchor.append("Moon")
    return AdmitOut(
        admitted=working.admitted,
        stamp=working.stamp,
        anchorage=(" and ".join(anchor) + " in the Anchorage"
                   if anchor else "moment outside the Anchorage"),
        assessments=[AssessmentOut(kind=a.claim.kind, text=a.claim.text,
                                   verdict=a.verdict, note=a.note)
                     for a in working.assessments],
        balance_holds=working.balance.holds,
        unbalanced_rights=working.balance.unbalanced,
        unresolved_duties=working.balance.unresolved_duties,
        ledger_id=ledger_id,
    )


# ------------------------------------------------------------------ gate
# "Prove all things; hold fast that which is good." -- 1 Thess. 5:21.
# These endpoints are the verse as infrastructure: every claim
# offered here is proven or marked, and only what is good -- no
# FALSEHOOD, balance holding -- is held fast (admitted).

@app.post("/admit", response_model=AdmitOut, tags=["gate"],
          summary="Weigh a working through the gate")
def post_admit(body: AdmitIn):
    """Offer claims; receive per-claim verdicts, the Oz x Duty balance,
    the stamp, and the admission. The working is written to the ledger.

    The verdict tallies are counted here (not in the ledger module)
    because they are the gate's reading of its own work -- the
    ledger stores the reading faithfully, but the reading itself
    belongs to the gate. The full payload (claims as submitted,
    stamp, admission) is stored verbatim as the witness statement.
    """
    claims = [_claim_from(c) for c in body.claims]
    working = admit(claims, duty_resolver=DUTY_RESOLVER, stamp=body.stamp,
                    sun_in_anchorage=body.sun_in_anchorage,
                    moon_in_anchorage=body.moon_in_anchorage)
    verdicts = {TRVVTH: 0, UNRESOLVED: 0, RHETORIC: 0, FALSEHOOD: 0}
    for a in working.assessments:
        verdicts[a.verdict] = verdicts.get(a.verdict, 0) + 1
    payload = {
        "claims": [c.model_dump() for c in body.claims],
        "stamp": working.stamp,
        "admitted": working.admitted,
    }
    ledger_id = db.record_admission(
        CONN, admitted=working.admitted, n_claims=len(claims),
        verdicts=verdicts, balance_holds=working.balance.holds,
        payload=payload)
    return _admit_out(working, ledger_id)


@app.post("/weigh", tags=["gate"], summary="Weigh one claim, no ledger")
def post_weigh(body: ClaimIn):
    """Weigh a single claim without recording a working. Useful for
    probing the gate or scripting checks -- the question "what would
    the gate say?" asked without committing the asking to the books.
    Some questions deserve weighing without witness; this is that
    endpoint."""
    assessment = weigh_claim(_claim_from(body))
    return {"kind": assessment.claim.kind, "text": assessment.claim.text,
            "verdict": assessment.verdict, "note": assessment.note}


@app.get("/kinds", tags=["gate"], summary="Claim kinds the gate weighs")
def get_kinds():
    """The four kinds, and the wire note that number-claims travel as
    expressions while Python callers may pass ``recompute``
    callables directly -- two doors into the same weighing room."""
    return {"kinds": list(KINDS),
            "note": "number-claims cross the wire with an arithmetic"
                    " expression; Python callers may pass recompute"
                    " callables directly."}


@app.get("/verdicts", tags=["gate"], summary="The four verdicts")
def get_verdicts():
    """The alethic axis as the API declares it: what each verdict
    means, and the cardinal rule beneath them all -- lack of proof is
    never scored as proof of falsehood. The axis cuts both ways: it
    judges claims, and it judges the judging.

    RHETORIC is the fourth verdict, and the one most easily
    misunderstood, so its meaning is stated plainly here: it files
    noise. An assertion offering no checkable content at all -- pure
    evaluation, insult, puffery -- is not "disproven" and not
    "unproven"; it never entered the jurisdiction of checking. The
    gate does not judge the speaker's character and does not rule on
    the statement's truth. It files the paper and moves on."""
    return {"verdicts": {
        TRVVTH: "the claim's grounds verify against the record",
        UNRESOLVED: "neither proven nor disproven -- marked for the human"
                    " red pen, never upgraded",
        RHETORIC: "no checkable content offered -- pure evaluation,"
                  " insult, or puffery; filed as noise, never judged,"
                  " never a conviction",
        FALSEHOOD: "the claim's grounds are fabricated, or the kind is"
                   " unknown"},
        "cardinal_rule": "Lack of proof is never scored as proof of"
                         " falsehood."}


@app.get("/cardinal-rules", tags=["gate"], summary="The gate's cardinal rules")
def get_rules():
    """The six rules, straight from the gate's own mouth
    (``trvvth.anchorage.cardinal_rules``) -- the API does not
    paraphrase doctrine, it serves it."""
    return {"rules": cardinal_rules()}


# ------------------------------------------------------------ diagnostics
# The gate examining itself: liveness, known answers, wiring, and
# the cost of its own labor. "The axis cuts both ways: it judges
# claims, and it judges the judging." -- trvvth.alethic.

@app.get("/diagnostics/health", tags=["diagnostics"], summary="Is the gate up?")
def health():
    """Liveness with identity: package name, version, and the
    declaration that the Anchorage is operational. A health check
    that cannot name what it guards is a pulse with no body."""
    return {"status": "ok", "package": "trvvth", "version": __version__,
            "gate": "anchorage operational", "ledger": True}


@app.post("/diagnostics/self-test", tags=["diagnostics"],
          summary="Known-answer suite against the live gate")
def self_test():
    """Seven checks with known verdicts, run through the real admit():

    1. verbatim quote -> TRVVTH (the gate recognizes its own proof)
    2. quote absent from source -> FALSEHOOD (exact quotes or none)
    3. number, expression recomputes -> TRVVTH (the wire form works)
    4. number, expression mismatches -> FALSEHOOD (arithmetic is honest)
    5. malformed citation -> FALSEHOOD (format is never truth)
    6. bare assertion -> UNRESOLVED (honest "not shown")
    7. pure rhetoric -> RHETORIC (noise filed, never judged)
    8. right without duty -> working not admitted (Oz x Duty is physics)

    The suite tests the *live* gate -- the same ``admit`` the API
    serves -- not a mock of it. A self-test that cannot fail the
    thing it tests is a ritual, not a diagnostic. ``healthy`` is
    True only when all eight pass.
    """
    checks = []
    w = admit([Claim(text="hold fast that which is good", kind="quote",
                     proof={"source": "prove all things; hold fast that"
                                     " which is good"})])
    checks.append(("verbatim quote is TRVVTH",
                   w.assessments[0].verdict == TRVVTH))
    w = admit([Claim(text="the moon is cheese", kind="quote",
                     proof={"source": "prove all things"})])
    checks.append(("absent quote is FALSEHOOD",
                   w.assessments[0].verdict == FALSEHOOD))
    w = admit([Claim(text="17+76", kind="number",
                     proof={"recompute": lambda: safe_evaluate("17+76"),
                            "expected": 93})])
    checks.append(("recomputed number is TRVVTH",
                   w.assessments[0].verdict == TRVVTH))
    w = admit([Claim(text="17+76", kind="number",
                     proof={"recompute": lambda: safe_evaluate("17+76"),
                            "expected": 94})])
    checks.append(("mismatched number is FALSEHOOD",
                   w.assessments[0].verdict == FALSEHOOD))
    w = admit([Claim(text="not a citation at all", kind="citation")])
    checks.append(("malformed citation is FALSEHOOD",
                   w.assessments[0].verdict == FALSEHOOD))
    w = admit([Claim(text="an unproven thing", kind="assertion")])
    checks.append(("bare assertion is UNRESOLVED",
                   w.assessments[0].verdict == UNRESOLVED))
    w = admit([Claim(text="he is nothing", kind="assertion")])
    checks.append(("pure rhetoric is RHETORIC, not FALSEHOOD",
                   w.assessments[0].verdict == RHETORIC
                   and w.admitted is True))
    w = admit([Claim(text="a right", kind="assertion", right="a right")])
    checks.append(("right without duty is not admitted",
                   w.admitted is False
                   and w.balance.holds is False))
    passed = sum(1 for _, ok in checks if ok)
    return {"passed": passed, "total": len(checks),
            "checks": [{"name": n, "ok": ok} for n, ok in checks],
            "healthy": passed == len(checks)}


@app.get("/diagnostics/wiring", tags=["diagnostics"],
         summary="What the gate is wired to")
def wiring():
    """Name the injections: which duty resolver (if any -- and any
    load error, honestly reported), that the stamp defaults to UTC
    unless the caller supplies one, and where the ledger file lives.
    The gate's wiring is injected, never assumed -- and never
    secret: this endpoint is the assumption, stated aloud."""
    return {
        "duty_resolver": ("open pairing (none wired)"
                          if DUTY_RESOLVER is None and not DUTY_RESOLVER_ERROR
                          else ("error: " + str(DUTY_RESOLVER_ERROR)
                                if DUTY_RESOLVER_ERROR
                                else os.environ.get("TRVVTH_DUTY_RESOLVER"))),
        "stamp": "UTC, unless the caller supplies one",
        "ledger": getattr(app.state, "ledger_path", None),
        "note": "Set TRVVTH_DUTY_RESOLVER=module:attribute to wire a"
                " strict duty registry; set TRVVTH_LEDGER to move the"
                " sqlite file.",
    }


@app.post("/diagnostics/benchmark", tags=["diagnostics"],
          summary="Benchmark the gate itself")
def run_benchmark(iterations: int = Query(1000, ge=10, le=100000)):
    """Time the gate's primitives (weigh per kind) and full workings
    (admit over 10/50/100 claims). The run is stored; compare against
    history via /diagnostics/benchmarks.

    The iteration count is bounded (10..100000): benchmarking is the
    counting of the cost, not the spending of it -- an unbounded
    benchmark endpoint would be a denial-of-service machine wearing
    a diagnostic's clothes. When a previous run exists, the response
    includes the per-benchmark delta: the gate weighed against
    itself, the axis judging the judging.
    """
    results = bench.run(iterations=iterations)
    run_id = db.record_benchmark(CONN, iterations=iterations,
                                 results=results)
    history = db.benchmark_history(CONN, limit=2)
    comparison = None
    if len(history) == 2:
        comparison = bench.compare(history[1]["results"], results)
    return {"run_id": run_id, "iterations": iterations,
            "results": results, "vs_previous": comparison}


@app.get("/diagnostics/benchmarks", tags=["diagnostics"],
         summary="Benchmark run history")
def benchmark_list(limit: int = Query(20, ge=1, le=100)):
    """Past benchmark runs, newest first -- the gate's speed as a
    record, not a rumor."""
    return {"runs": db.benchmark_history(CONN, limit=limit)}


@app.get("/diagnostics/benchmarks/{run_id}", tags=["diagnostics"],
         summary="One benchmark run")
def benchmark_one(run_id: int):
    """One run by id, in full. A missing id is a 404 -- the honest
    "not shown" rather than an invented empty run."""
    run = db.benchmark_run(CONN, run_id)
    if run is None:
        raise HTTPException(404, "no such benchmark run")
    return run


# ---------------------------------------------------------------- reports
# "At the mouth of two witnesses... shall the matter be
# established." -- Deut. 19:15. The reports are the second witness:
# the gate weighed the working, and the ledger testifies that the
# weighing happened.

@app.get("/reports/ledger", tags=["reports"], summary="Admission ledger")
def reports_ledger(limit: int = Query(50, ge=1, le=500),
                   offset: int = Query(0, ge=0),
                   admitted: Optional[bool] = None):
    """Page the admissions book, newest first, with an optional
    admitted/not-admitted filter. The page names the workings; the
    full witness statement behind each is one more query away."""
    return {"workings": db.ledger_page(CONN, limit=limit, offset=offset,
                                       admitted=admitted)}


@app.get("/reports/summary", tags=["reports"], summary="Ledger summary")
def reports_summary():
    """The whole book tallied in one reading: workings, admission
    rate, claims, verdicts, balances held."""
    return db.admission_summary(CONN)


@app.get("/reports/charts/verdicts", tags=["reports"],
         summary="SVG: verdict distribution")
def chart_verdicts():
    """The alethic account as a picture: the three verdicts in their
    doctrinal colors, served as dependency-free SVG."""
    return Response(content=svg.verdict_chart(db.verdict_counts(CONN)),
                    media_type="image/svg+xml")


@app.get("/reports/charts/timeline", tags=["reports"],
         summary="SVG: workings per day")
def chart_timeline(days: int = Query(30, ge=1, le=365)):
    """Workings per day over the trailing window -- the gate's labor
    as a rhythm, so the operator can see when the gate worked and
    when it rested."""
    pts = [(d["day"], d["workings"]) for d in db.daily_workings(CONN, days)]
    return Response(
        content=svg.timeline("Workings per Day", pts,
                             subtitle=f"last {days} days"),
        media_type="image/svg+xml")


@app.get("/reports/charts/kinds", tags=["reports"],
         summary="SVG: claims by kind")
def chart_kinds():
    """What the gate has been asked to weigh, by kind -- the shape
    of the questions, not just the shape of the answers."""
    items = sorted(db.claims_by_kind(CONN).items())
    return Response(
        content=svg.bar_chart("Claims by Kind", [(k, float(v)) for k, v in items],
                              subtitle="all workings on the ledger"),
        media_type="image/svg+xml")


# --------------------------------------------------------------- analytics
# "To every thing there is a season, and a time to every purpose
# under the heaven." -- Ecclesiastes 3:1. Analytics is the
# bookkeeping of times: when the requests came, how long each
# labored, and which ended in failure. The app watches itself the
# way the gate watches claims -- by witness, not by assumption.

@app.get("/analytics/overview", tags=["analytics"],
         summary="The app watching itself")
def analytics_overview():
    """Two self-portraits side by side: the app's (requests,
    latency, error rate, hottest paths) and the gate's (workings,
    admission rate, verdicts). The server grading its own labor,
    honestly -- including the failures, which are counted, not
    hidden."""
    stats = db.request_stats(CONN)
    gate = db.admission_summary(CONN)
    return {"app": stats, "gate": gate}


@app.get("/analytics/charts/traffic", tags=["analytics"],
         summary="SVG: requests per endpoint")
def chart_traffic():
    """Which doors the world knocks on: request counts for the
    twelve hottest endpoints. The gate's popularity contest, drawn
    without flattery."""
    items = [(r["path"], float(r["hits"]))
             for r in db.request_stats(CONN)["by_path"][:12]]
    return Response(
        content=svg.bar_chart("Requests per Endpoint", items,
                              subtitle="this server, all time"),
        media_type="image/svg+xml")


@app.get("/analytics/charts/latency", tags=["analytics"],
         summary="SVG: mean latency over time")
def chart_latency():
    """Mean latency in five-minute buckets -- the server's pulse as
    a timeline. Timestamps are rendered in the server's local time;
    the underlying buckets are UTC, because the stamp says when and
    the chart shows it."""
    pts = [(time.strftime("%m-%d %H:%M", time.localtime(p["ts"])), p["avg_ms"])
           for p in db.latency_series(CONN)]
    return Response(
        content=svg.timeline("Mean Latency (ms)", pts,
                             subtitle="5-minute buckets", color="#2e7d6f"),
        media_type="image/svg+xml")


@app.get("/analytics/charts/benchmarks", tags=["analytics"],
         summary="SVG: gate throughput across runs")
def chart_benchmarks():
    """Throughput per benchmark across the last ten runs, grouped --
    the gate's speed as a history, so a slowdown is visible before
    it is felt. With no runs yet, the chart says so plainly rather
    than drawing an empty frame and calling it data."""
    history = list(reversed(db.benchmark_history(CONN, limit=10)))
    series: dict[str, list[tuple[str, float]]] = {}
    for run in history:
        label = f"run {run['id']}"
        for name, res in run["results"].items():
            series.setdefault(name, []).append(
                (label, res["ops_per_second"]))
    if not series:
        series = {"no runs yet": [("run -", 0.0)]}
    return Response(
        content=svg.multi_series("Gate Throughput (ops/sec)", series,
                                 subtitle="benchmark history, latest last"),
        media_type="image/svg+xml")


# ------------------------------------------------------------------- docs
# "The Method of Science, the Aim of Religion." The guide is the
# method written down: the narrative form of the machine-readable
# schema, so the operator learns the gate the way the schema cannot
# teach -- by story and example.

_GUIDE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>TRVVTH API -- Operator's Guide</title>
<style>body{font-family:Georgia,serif;max-width:46em;margin:2em auto;
padding:0 1em;color:#1a1a2e;background:#faf8f2;line-height:1.55}
h1,h2{color:#1a1a2e}code{background:#efe9da;padding:0 .3em;border-radius:3px}
pre{background:#1a1a2e;color:#faf8f2;padding:1em;overflow-x:auto;
border-radius:6px}pre code{background:none;color:inherit}
a{color:#3b3b6d}</style></head><body>
<h1>TRVVTH API -- Operator's Guide</h1>
<p>The zero-trust gate over HTTP. Claims in, verdicts out, no trust
assumed. Interactive schema at <a href="/docs">/docs</a>,
ReDoc at <a href="/redoc">/redoc</a>.</p>
<h2>The gate</h2>
<p><code>POST /admit</code> weighs a working. Each claim carries
<code>text</code>, <code>kind</code> (quote | number | citation |
assertion), <code>proof</code>, and optional <code>right</code> /
<code>duty</code>:</p>
<pre><code>{
  "claims": [
    {"text": "hold fast that which is good", "kind": "quote",
     "proof": {"source": "prove all things; hold fast that which is good"}},
    {"text": "17+76", "kind": "number",
     "proof": {"expression": "17+76", "expected": 93},
     "right": "to publish", "duty": "to verify"}
  ]
}</code></pre>
<p>Quotes are TRVVTH iff verbatim in the source. Numbers are TRVVTH
iff the arithmetic <code>expression</code> recomputes to
<code>expected</code> (operators <code>+ - * / // % **</code> and
parentheses only -- evaluated by a safe parser, never
<code>eval</code>). Citations are never TRVVTH from format alone.
Assertions without proof are UNRESOLVED. Assertions offering no
checkable content at all -- pure evaluation, insult, puffery -- are
filed as RHETORIC: noise, never judged, never a conviction. A right without its duty
unbalances the working and it is not admitted.</p>
<p><code>POST /weigh</code> weighs one claim without touching the
ledger. <code>GET /kinds</code>, <code>/verdicts</code>,
<code>/cardinal-rules</code> serve reference data.</p>
<h2>Diagnostics</h2>
<ul><li><code>GET /diagnostics/health</code> -- liveness.</li>
<li><code>POST /diagnostics/self-test</code> -- eight known-answer
checks run through the live gate.</li>
<li><code>GET /diagnostics/wiring</code> -- duty resolver, stamp
source, ledger path.</li>
<li><code>POST /diagnostics/benchmark?iterations=1000</code> --
times weigh-per-kind and admit over 10/50/100-claim workings; the run
is stored and compared against the previous run.</li>
<li><code>GET /diagnostics/benchmarks</code> and
<code>/diagnostics/benchmarks/{id}</code> -- run history.</li></ul>
<h2>Reports</h2>
<p>Every admission is written to a sqlite ledger (env
<code>TRVVTH_LEDGER</code>, default <code>trvvth-ledger.db</code>).
<code>GET /reports/ledger</code> pages it,
<code>GET /reports/summary</code> tallies it, and
<code>/reports/charts/verdicts</code>,
<code>/reports/charts/timeline</code>,
<code>/reports/charts/kinds</code> serve SVG charts.</p>
<h2>Analytics</h2>
<p>The app watches itself: every request's method, path, status, and
duration is recorded.
<code>GET /analytics/overview</code> returns traffic, latency, and
error stats alongside gate totals;
<code>/analytics/charts/traffic</code>,
<code>/analytics/charts/latency</code>, and
<code>/analytics/charts/benchmarks</code> serve SVG charts.</p>
<h2>Serving</h2>
<pre><code>trvvth-serve --port 8124
TRVVTH_LEDGER=/var/lib/trvvth.db \\
TRVVTH_DUTY_RESOLVER=mymod:resolve_duty \\
trvvth-serve --host 0.0.0.0 --port 8124</code></pre>
<p style="color:#6b6b7d">TRVVTH v{ver} -- Johnathan 'Qasparr'
(&Kappa;&alpha;&sigma;&pi;&#x3AC;&rho;&rho;) Monroe. AGPL-3.0-only.</p>
</body></html>"""


@app.get("/guide", response_class=HTMLResponse, tags=["docs"],
         summary="Operator's guide")
def guide():
    """The narrative documentation: the method written down. The
    machine-readable schema teaches the shapes; the guide teaches
    the gate -- by story and example, the way the schema cannot."""
    return _GUIDE.replace("{ver}", __version__)


@app.get("/", response_class=HTMLResponse, tags=["docs"], include_in_schema=False)
def index():
    """The front door: version, and the three ways in -- the guide,
    the interactive schema, and the health check. Kept out of the
    OpenAPI schema deliberately: it is a signpost, not an endpoint."""
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>TRVVTH -- the Zero-Trust Anchorage</title>
<style>body{{font-family:Georgia,serif;max-width:40em;margin:3em auto;
padding:0 1em;background:#faf8f2;color:#1a1a2e;line-height:1.6}}
a{{color:#3b3b6d}}</style></head><body>
<h1>TRVVTH</h1><p>The zero-trust gate as an API. v{__version__}.</p>
<ul><li><a href="/guide">Operator's guide</a></li>
<li><a href="/docs">Interactive API docs (Swagger)</a></li>
<li><a href="/redoc">ReDoc</a></li>
<li><a href="/diagnostics/health">Health</a></li>
<li><a href="/reports/charts/verdicts">Verdict chart</a></li></ul>
<p>Claims in, verdicts out, no trust assumed.</p></body></html>"""


@app.exception_handler(404)
async def _not_found(request: Request, exc):
    """The 404 with doctrine: an unknown route is not an error to be
    feared but a question the gate cannot answer -- and the gate's
    honest answer to what it cannot answer is UNRESOLVED, never
    FALSEHOOD. Even the error handler keeps the cardinal rule."""
    return JSONResponse(status_code=404,
                        content={"verdict": "UNRESOLVED",
                                 "note": f"no such route: {request.url.path}"})
