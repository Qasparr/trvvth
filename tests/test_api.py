# test_api -- the TRVVTH HTTP API, diagnostics, reports, analytics, benchmarks.
# Run directly: python tests/test_api.py (asserts; prints "N tests passed").
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_LEDGER = "/tmp/test-trvvth-ledger.db"
if os.path.exists(_LEDGER):
    os.remove(_LEDGER)
os.environ["TRVVTH_LEDGER"] = _LEDGER

from trvvth import safeval, charts, benchmarks  # noqa: E402
from trvvth.safeval import evaluate  # noqa: E402

passed = 0


def check(name, cond):
    global passed
    assert cond, f"FAILED: {name}"
    passed += 1


# --- safeval ---
check("17+76 == 93", evaluate("17+76") == 93)
check("parens and pow", evaluate("(2+3)**2") == 25)
check("unary minus", evaluate("-5+8") == 3)
for bad in ["__import__('os')", "open('x')", "1+2; 3", "a+1", "", "9" * 201]:
    try:
        evaluate(bad)
        raise SystemExit(f"FAILED: safeval accepted {bad!r}")
    except ValueError:
        passed += 1
check("safeval rejects 6 hostile inputs", True)

# --- charts ---
svg = charts.verdict_chart({"TRVVTH": 3, "UNRESOLVED": 1, "FALSEHOOD": 0})
check("verdict chart is svg", svg.startswith("<svg") and "TRVVTH" in svg)
check("timeline is svg",
      charts.timeline("T", [("2026-01-01", 2)]).startswith("<svg"))
check("multi_series is svg",
      charts.multi_series("T", {"a": [("x", 1.0)]}).startswith("<svg"))
check("bar chart is svg",
      charts.bar_chart("T", [("k", 5.0)]).startswith("<svg"))

# --- benchmarks ---
res = benchmarks.run(iterations=20)
for name in ("weigh_quote", "weigh_number", "weigh_citation",
             "weigh_assertion", "admit_10_claims", "admit_50_claims",
             "admit_100_claims"):
    check(f"bench {name} has ops/sec", res[name]["ops_per_second"] > 0)
cmp_ = benchmarks.compare(res, res)
check("compare identical is ~0%",
      all(abs(v["delta_pct"]) < 0.01 for v in cmp_.values()))

# --- API ---
from fastapi.testclient import TestClient  # noqa: E402
from trvvth.api import app  # noqa: E402

with TestClient(app) as client:
    r = client.get("/diagnostics/health")
    check("health ok", r.json()["status"] == "ok")

    r = client.post("/diagnostics/self-test")
    body = r.json()
    check("self-test healthy", body["healthy"] is True)
    check("self-test 8 checks", body["total"] == 8)

    r = client.get("/diagnostics/wiring")
    check("wiring reports ledger", "ledger" in r.json())

    good = {"claims": [
        {"text": "hold fast that which is good", "kind": "quote",
         "proof": {"source": "prove all things; hold fast that which is good"}},
        {"text": "17+76", "kind": "number",
         "proof": {"expression": "17+76", "expected": 93},
         "right": "to publish", "duty": "to verify"},
    ]}
    r = client.post("/admit", json=good)
    body = r.json()
    check("admit good working", body["admitted"] is True)
    check("admit verdicts TRVVTH",
          all(a["verdict"] == "TRVVTH" for a in body["assessments"]))
    check("admit ledger id", body["ledger_id"] >= 1)

    bad = {"claims": [{"text": "a right", "kind": "assertion",
                       "right": "a right"}]}
    r = client.post("/admit", json=bad)
    body = r.json()
    check("right without duty not admitted", body["admitted"] is False)
    check("unbalanced reported", body["unbalanced_rights"] == ["a right"])

    r = client.post("/weigh", json={"text": "x", "kind": "assertion"})
    check("weigh single", r.json()["verdict"] == "UNRESOLVED")

    # RHETORIC over the wire: pure evaluation files as noise, and
    # the filing is not a conviction -- the working is admitted.
    r = client.post("/weigh", json={"text": "you are an idiot",
                                    "kind": "assertion"})
    check("weigh rhetoric", r.json()["verdict"] == "RHETORIC")
    r = client.post("/admit", json={"claims": [
        {"text": "he is nothing", "kind": "assertion"}]})
    body = r.json()
    check("admit rhetoric verdict",
          body["assessments"][0]["verdict"] == "RHETORIC")
    check("admit rhetoric not refused", body["admitted"] is True)

    r = client.get("/kinds")
    check("kinds", "quote" in r.json()["kinds"])
    r = client.get("/verdicts")
    check("verdicts", "TRVVTH" in r.json()["verdicts"])
    check("verdicts has RHETORIC", "RHETORIC" in r.json()["verdicts"])
    r = client.get("/cardinal-rules")
    check("rules", len(r.json()["rules"]) == 6)

    r = client.get("/reports/summary")
    check("summary workings", r.json()["workings"] >= 2)

    r = client.get("/reports/ledger?limit=10")
    check("ledger page", len(r.json()["workings"]) >= 2)
    r = client.get("/reports/ledger?admitted=false")
    check("ledger filter", all(not w["admitted"]
                               for w in r.json()["workings"]))

    for path in ("/reports/charts/verdicts", "/reports/charts/timeline",
                 "/reports/charts/kinds"):
        r = client.get(path)
        check(f"chart {path}",
              r.headers["content-type"] == "image/svg+xml"
              and r.text.startswith("<svg"))

    r = client.get("/analytics/overview")
    ov = r.json()
    check("analytics has requests", ov["app"]["total_requests"] > 0)
    check("analytics has gate totals", ov["gate"]["workings"] >= 2)
    check("analytics latency", ov["app"]["avg_latency_ms"] >= 0)

    for path in ("/analytics/charts/traffic", "/analytics/charts/latency"):
        r = client.get(path)
        check(f"analytics chart {path}",
              r.headers["content-type"] == "image/svg+xml")

    r = client.post("/diagnostics/benchmark?iterations=20")
    body = r.json()
    check("benchmark run", body["run_id"] >= 1
          and "weigh_quote" in body["results"])
    run_id = body["run_id"]
    r = client.get("/diagnostics/benchmarks")
    check("benchmark history", len(r.json()["runs"]) >= 1)
    r = client.get(f"/diagnostics/benchmarks/{run_id}")
    check("benchmark one", r.json()["id"] == run_id)
    r = client.get("/diagnostics/benchmarks/999999")
    check("benchmark 404", r.status_code == 404)

    r = client.get("/analytics/charts/benchmarks")
    check("benchmark chart svg",
          r.headers["content-type"] == "image/svg+xml"
          and r.text.startswith("<svg"))

    r = client.get("/guide")
    check("guide html", "Operator's Guide" in r.text)
    r = client.get("/")
    check("index html", "TRVVTH" in r.text)

    r = client.get("/no-such-route")
    check("404 is UNRESOLVED", r.status_code == 404
          and r.json()["verdict"] == "UNRESOLVED")

    r = client.get("/docs")
    check("swagger docs", r.status_code == 200)

print(f"{passed} tests passed")
