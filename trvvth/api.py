# Johnathan 'Qasparr' (Κασπάρρ) Monroe, Keeper of the Secret Treasure
# All Rights Reserved, Without Prejudice.  CashApp $axoneme
"""api -- the TRVVTH gate as a cross-platform HTTP API.

Pure Python + FastAPI: it runs anywhere Python runs. Every surface
is reachable over HTTP and documented three ways -- OpenAPI at
``/docs``, ReDoc at ``/redoc``, and the hand-written operator's guide
at ``/guide``.

Surfaces:
* the gate itself: POST /admit, POST /weigh, plus reference data
  (kinds, verdicts, cardinal rules);
* diagnostics: health, a known-answer self-test, wiring report, and
  the gate's own benchmark suite with run history;
* reports: the admission ledger, summaries, and SVG charts;
* analytics: the app watching itself -- request counts, latency,
  error rates, and their charts.

Number-claims cross the wire with ``proof: {"expression": "17+76",
"expected": 93}``; the expression is evaluated by trvvth.safeval
(no eval, no names, arithmetic only). Python callers can keep using
``recompute`` callables directly against trvvth.anchorage.

Persistence: one sqlite file (env TRVVTH_LEDGER, default
./trvvth-ledger.db) holding admissions, request analytics, and
benchmark runs. Stdlib only -- nothing to install, nothing
platform-specific.
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
from .alethic import FALSEHOOD, TRVVTH, UNRESOLVED
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

class ClaimIn(BaseModel):
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
    claims: list[ClaimIn] = Field(..., min_length=1)
    stamp: Optional[str] = Field(None, description="Override the UTC stamp.")
    sun_in_anchorage: bool = False
    moon_in_anchorage: bool = False


class AssessmentOut(BaseModel):
    kind: str
    text: str
    verdict: str
    note: str


class AdmitOut(BaseModel):
    admitted: bool
    stamp: str
    anchorage: str
    assessments: list[AssessmentOut]
    balance_holds: bool
    unbalanced_rights: list[str]
    unresolved_duties: list[str]
    ledger_id: int


# ------------------------------------------------------- wiring & lifespan

def _load_duty_resolver():
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
    proof = dict(data.proof)
    if data.kind == "number" and "expression" in proof:
        expression = proof.pop("expression")
        expected = proof.get("expected")
        proof["recompute"] = (lambda e=expression: safe_evaluate(e))
        proof["expected"] = expected
    return Claim(text=data.text, kind=data.kind, proof=proof,
                 right=data.right, duty=data.duty)


def _admit_out(working, ledger_id: int) -> AdmitOut:
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

@app.post("/admit", response_model=AdmitOut, tags=["gate"],
          summary="Weigh a working through the gate")
def post_admit(body: AdmitIn):
    """Offer claims; receive per-claim verdicts, the Oz x Duty balance,
    the stamp, and the admission. The working is written to the ledger."""
    claims = [_claim_from(c) for c in body.claims]
    working = admit(claims, duty_resolver=DUTY_RESOLVER, stamp=body.stamp,
                    sun_in_anchorage=body.sun_in_anchorage,
                    moon_in_anchorage=body.moon_in_anchorage)
    verdicts = {TRVVTH: 0, UNRESOLVED: 0, FALSEHOOD: 0}
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
    probing the gate or scripting checks."""
    assessment = weigh_claim(_claim_from(body))
    return {"kind": assessment.claim.kind, "text": assessment.claim.text,
            "verdict": assessment.verdict, "note": assessment.note}


@app.get("/kinds", tags=["gate"], summary="Claim kinds the gate weighs")
def get_kinds():
    return {"kinds": list(KINDS),
            "note": "number-claims cross the wire with an arithmetic"
                    " expression; Python callers may pass recompute"
                    " callables directly."}


@app.get("/verdicts", tags=["gate"], summary="The three verdicts")
def get_verdicts():
    return {"verdicts": {
        TRVVTH: "the claim's grounds verify against the record",
        UNRESOLVED: "neither proven nor disproven -- marked for the human"
                    " red pen, never upgraded",
        FALSEHOOD: "the claim's grounds are fabricated, or the kind is"
                   " unknown"},
        "cardinal_rule": "Lack of proof is never scored as proof of"
                         " falsehood."}


@app.get("/cardinal-rules", tags=["gate"], summary="The gate's cardinal rules")
def get_rules():
    return {"rules": cardinal_rules()}


# ------------------------------------------------------------ diagnostics

@app.get("/diagnostics/health", tags=["diagnostics"], summary="Is the gate up?")
def health():
    return {"status": "ok", "package": "trvvth", "version": __version__,
            "gate": "anchorage operational", "ledger": True}


@app.post("/diagnostics/self-test", tags=["diagnostics"],
          summary="Known-answer suite against the live gate")
def self_test():
    """Six checks with known verdicts, run through the real admit():

    1. verbatim quote -> TRVVTH
    2. quote absent from source -> FALSEHOOD
    3. number, expression recomputes -> TRVVTH
    4. number, expression mismatches -> FALSEHOOD
    5. malformed citation -> FALSEHOOD
    6. bare assertion -> UNRESOLVED
    7. right without duty -> working not admitted
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
    history via /diagnostics/benchmarks."""
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
    return {"runs": db.benchmark_history(CONN, limit=limit)}


@app.get("/diagnostics/benchmarks/{run_id}", tags=["diagnostics"],
         summary="One benchmark run")
def benchmark_one(run_id: int):
    run = db.benchmark_run(CONN, run_id)
    if run is None:
        raise HTTPException(404, "no such benchmark run")
    return run


# ---------------------------------------------------------------- reports

@app.get("/reports/ledger", tags=["reports"], summary="Admission ledger")
def reports_ledger(limit: int = Query(50, ge=1, le=500),
                   offset: int = Query(0, ge=0),
                   admitted: Optional[bool] = None):
    return {"workings": db.ledger_page(CONN, limit=limit, offset=offset,
                                       admitted=admitted)}


@app.get("/reports/summary", tags=["reports"], summary="Ledger summary")
def reports_summary():
    return db.admission_summary(CONN)


@app.get("/reports/charts/verdicts", tags=["reports"],
         summary="SVG: verdict distribution")
def chart_verdicts():
    return Response(content=svg.verdict_chart(db.verdict_counts(CONN)),
                    media_type="image/svg+xml")


@app.get("/reports/charts/timeline", tags=["reports"],
         summary="SVG: workings per day")
def chart_timeline(days: int = Query(30, ge=1, le=365)):
    pts = [(d["day"], d["workings"]) for d in db.daily_workings(CONN, days)]
    return Response(
        content=svg.timeline("Workings per Day", pts,
                             subtitle=f"last {days} days"),
        media_type="image/svg+xml")


@app.get("/reports/charts/kinds", tags=["reports"],
         summary="SVG: claims by kind")
def chart_kinds():
    items = sorted(db.claims_by_kind(CONN).items())
    return Response(
        content=svg.bar_chart("Claims by Kind", [(k, float(v)) for k, v in items],
                              subtitle="all workings on the ledger"),
        media_type="image/svg+xml")


# --------------------------------------------------------------- analytics

@app.get("/analytics/overview", tags=["analytics"],
         summary="The app watching itself")
def analytics_overview():
    stats = db.request_stats(CONN)
    gate = db.admission_summary(CONN)
    return {"app": stats, "gate": gate}


@app.get("/analytics/charts/traffic", tags=["analytics"],
         summary="SVG: requests per endpoint")
def chart_traffic():
    items = [(r["path"], float(r["hits"]))
             for r in db.request_stats(CONN)["by_path"][:12]]
    return Response(
        content=svg.bar_chart("Requests per Endpoint", items,
                              subtitle="this server, all time"),
        media_type="image/svg+xml")


@app.get("/analytics/charts/latency", tags=["analytics"],
         summary="SVG: mean latency over time")
def chart_latency():
    pts = [(time.strftime("%m-%d %H:%M", time.localtime(p["ts"])), p["avg_ms"])
           for p in db.latency_series(CONN)]
    return Response(
        content=svg.timeline("Mean Latency (ms)", pts,
                             subtitle="5-minute buckets", color="#2e7d6f"),
        media_type="image/svg+xml")


@app.get("/analytics/charts/benchmarks", tags=["analytics"],
         summary="SVG: gate throughput across runs")
def chart_benchmarks():
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
Assertions without proof are UNRESOLVED. A right without its duty
unbalances the working and it is not admitted.</p>
<p><code>POST /weigh</code> weighs one claim without touching the
ledger. <code>GET /kinds</code>, <code>/verdicts</code>,
<code>/cardinal-rules</code> serve reference data.</p>
<h2>Diagnostics</h2>
<ul><li><code>GET /diagnostics/health</code> -- liveness.</li>
<li><code>POST /diagnostics/self-test</code> -- seven known-answer
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
    return _GUIDE.replace("{ver}", __version__)


@app.get("/", response_class=HTMLResponse, tags=["docs"], include_in_schema=False)
def index():
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
    return JSONResponse(status_code=404,
                        content={"verdict": "UNRESOLVED",
                                 "note": f"no such route: {request.url.path}"})
