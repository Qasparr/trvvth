# ☉ in 4° 34′ Libra  ☽ in 16° 47′ Aries  dies solis  Anno V:xii e.n.
# Johnathan 'Qasparr' (Κασπάρρ) Monroe, Keeper of the Secret Treasure
# All Rights Reserved, Without Prejudice.  CashApp $axoneme
"""
Validation tests for trvvth.anchorage -- the Zero-Trust Anchorage,
standalone (no persona imports; duty registry and clock injected).

Run:  python3 tests/test_gate.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from trvvth import (  # noqa: E402
    ASSERTION,
    CITATION,
    FALSEHOOD,
    NUMBER,
    QUOTE,
    RHETORIC,
    TRVVTH,
    UNRESOLVED,
    Claim,
    admit,
    cardinal_rules,
    detect_rhetoric,
    weigh_claim,
    weigh_rights,
)

PASS = 0


def check(label, fn):
    global PASS
    try:
        fn()
    except AssertionError as e:
        print(f"FAIL  {label}: {e}")
        raise SystemExit(1)
    PASS += 1
    print(f"  ok: {label}")


def t_quote_verbatim_is_trvvth():
    c = Claim(text="exact words", kind=QUOTE, proof={"source": "these exact words here"})
    assert weigh_claim(c).verdict == TRVVTH


def t_quote_missing_is_falsehood():
    c = Claim(text="other words", kind=QUOTE, proof={"source": "these exact words here"})
    assert weigh_claim(c).verdict == FALSEHOOD


def t_quote_no_source_is_unresolved():
    assert weigh_claim(Claim(text="x", kind=QUOTE)).verdict == UNRESOLVED


def t_number_recomputed_is_trvvth():
    c = Claim(text="93", kind=NUMBER,
              proof={"recompute": lambda: 93, "expected": 93})
    a = weigh_claim(c)
    assert a.verdict == TRVVTH, a.note


def t_number_mismatch_is_falsehood():
    c = Claim(text="93", kind=NUMBER,
              proof={"recompute": lambda: 94, "expected": 93})
    assert weigh_claim(c).verdict == FALSEHOOD


def t_number_no_recompute_is_unresolved():
    assert weigh_claim(Claim(text="93", kind=NUMBER)).verdict == UNRESOLVED


def t_number_crashing_recompute_is_unresolved():
    def boom():
        raise ValueError("nope")
    c = Claim(text="93", kind=NUMBER, proof={"recompute": boom, "expected": 93})
    a = weigh_claim(c)
    assert a.verdict == UNRESOLVED, a.note  # the gate reports, never crashes


def t_citation_plausible_is_unresolved():
    c = Claim(text="319 U.S. 105 (1943)", kind=CITATION)
    a = weigh_claim(c)
    assert a.verdict == UNRESOLVED and "red pen" in a.note, a.note


def t_citation_malformed_is_falsehood():
    assert weigh_claim(Claim(text="some case, I think", kind=CITATION)).verdict == FALSEHOOD


def t_citation_full_form_case_cite_is_unresolved():
    # The QIRA audit (2026-10-01) caught the gate rejecting a proper
    # full-form cite while accepting the bare reporter half. Format
    # plausibility earns the red pen -- UNRESOLVED -- never TRVVTH.
    a = weigh_claim(
        Claim(text="SEC v. W.J. Howey Co., 328 U.S. 293 (1946)", kind=CITATION))
    assert a.verdict == UNRESOLVED and "red pen" in a.note, a.note
    assert a.verdict != TRVVTH


def t_citation_bare_reporter_still_unresolved():
    a = weigh_claim(Claim(text="328 U.S. 293 (1946)", kind=CITATION))
    assert a.verdict == UNRESOLVED and "red pen" in a.note, a.note


def t_assertion_is_unresolved():
    a = weigh_claim(Claim(text="a bare claim", kind=ASSERTION))
    assert a.verdict == UNRESOLVED, a.note


def t_unknown_kind_is_falsehood():
    assert weigh_claim(Claim(text="x", kind="rumor")).verdict == FALSEHOOD


def t_cardinal_rule_lack_of_proof():
    # The cardinal rule: UNRESOLVED is never upgraded, never convicted.
    rules = cardinal_rules()
    assert any("never scored as proof of falsehood" in r for r in rules)


def t_balance_holds_when_paired():
    b = weigh_rights([Claim(text="x", kind=ASSERTION, right="speech", duty="care")])
    assert b.holds and b.unbalanced == []


def t_balance_fails_when_unpaired():
    b = weigh_rights([Claim(text="x", kind=ASSERTION, right="speech")])
    assert not b.holds and b.unbalanced == ["speech"]


def t_balance_no_resolver_takes_duty_at_face_value():
    b = weigh_rights([Claim(text="x", kind=ASSERTION, right="r", duty="whatever")])
    assert b.unresolved_duties == [], "no resolver wired: cannot judge duties"


def t_balance_resolver_marks_unresolved():
    b = weigh_rights([Claim(text="x", kind=ASSERTION, right="r", duty="bogus")],
                     duty_resolver=lambda d: {"real": "REAL"}.get(d))
    assert b.unresolved_duties == ["r"], b.unresolved_duties


def t_admit_clean_claims_admitted():
    w = admit([Claim(text="2+2", kind=NUMBER,
                     proof={"recompute": lambda: 4, "expected": 4})],
              stamp="test-stamp")
    assert w.admitted and w.stamp == "test-stamp", w.report()


def t_admit_falsehood_refuses():
    w = admit([Claim(text="nope", kind=QUOTE, proof={"source": "other"})])
    assert not w.admitted


def t_admit_unbalanced_refuses():
    w = admit([Claim(text="x", kind=ASSERTION, right="r")])
    assert not w.admitted
    assert "UNBALANCED" in w.report()


def t_admit_unresolved_marked_never_upgraded():
    w = admit([Claim(text="maybe", kind=ASSERTION)])
    assert w.admitted, "UNRESOLVED alone does not refuse"
    assert w.assessments[0].verdict == UNRESOLVED


def t_admit_default_stamp_is_utc():
    w = admit([])
    assert "T" in w.stamp, w.stamp  # ISO-8601 UTC default


def t_admit_injected_clock():
    w = admit([], stamp="dies solis", sun_in_anchorage=True)
    assert "Sun in the Anchorage" in w.report(), w.report()


def t_no_persona_imports():
    import trvvth.anchorage as a
    import trvvth.alethic as x
    assert "persona_v" not in getattr(a, "__file__", "")
    assert "persona_v" not in getattr(x, "__file__", "")


# ------------------------------------------------------- RHETORIC (v0.2.2)
# The fourth verdict: pure evaluation with no checkable content is
# filed as noise, never judged. These tests pin both directions --
# rhetoric fires only on the uncheckable, and UNRESOLVED keeps
# everything that might be a claim.

def t_rhetoric_insult_is_rhetoric():
    a = weigh_claim(Claim(text="You are an idiot", kind=ASSERTION))
    assert a.verdict == RHETORIC, a.note
    assert "no checkable content" in a.note


def t_rhetoric_tonights_claim_is_rhetoric():
    # The claim from the night of 2026-10-01 that motivated the
    # verdict: filed as noise, not convicted of falsehood.
    a = weigh_claim(Claim(
        text="Johnathan Monroe is nothing; his work amounts to nothing.",
        kind=ASSERTION))
    assert a.verdict == RHETORIC, a.note


def t_rhetoric_puffery_is_rhetoric():
    assert weigh_claim(
        Claim(text="This is the best", kind=ASSERTION)).verdict == RHETORIC
    assert weigh_claim(
        Claim(text="She was pathetic", kind=ASSERTION)).verdict == RHETORIC


def t_rhetoric_does_not_refuse_admission():
    # Filing is not conviction: RHETORIC is not FALSEHOOD, so the
    # working is still admitted. The gate puts the paper in a
    # drawer; it does not bar the door.
    w = admit([Claim(text="he is nothing", kind=ASSERTION)])
    assert w.admitted, "RHETORIC alone must not refuse"
    assert w.assessments[0].verdict == RHETORIC


def t_rhetoric_digit_veto_keeps_unresolved():
    # Any checkable thread vetoes: a number is something a checker
    # could pursue, so the claim might be a claim.
    a = weigh_claim(Claim(text="The answer is 42, trust me", kind=ASSERTION))
    assert a.verdict == UNRESOLVED, a.note


def t_rhetoric_mixed_claim_stays_unresolved():
    a = weigh_claim(Claim(text="He is terrible and he stole $50",
                          kind=ASSERTION))
    assert a.verdict == UNRESOLVED, a.note


def t_rhetoric_denial_stays_unresolved():
    # "is not stupid" is a denial, not an evaluation -- it belongs
    # to whoever would defend the subject.
    a = weigh_claim(Claim(text="He is not stupid", kind=ASSERTION))
    assert a.verdict == UNRESOLVED, a.note


def t_rhetoric_quoted_evaluation_stays_unresolved():
    # Quoted evaluation is quotable against its source: the claim is
    # "she said it", which a checker could pursue.
    a = weigh_claim(Claim(text='"He is nothing," she said', kind=ASSERTION))
    assert a.verdict == UNRESOLVED, a.note


def t_rhetoric_year_veto_keeps_unresolved():
    a = weigh_claim(Claim(text="In 2020 he was the worst", kind=ASSERTION))
    assert a.verdict == UNRESOLVED, a.note


def t_rhetoric_link_veto_keeps_unresolved():
    a = weigh_claim(Claim(
        text="The service is awful: https://example.com/report",
        kind=ASSERTION))
    assert a.verdict == UNRESOLVED, a.note


def t_rhetoric_trailing_noun_is_not_predicate():
    # "is the best evidence we have" -- "evidence" follows "best",
    # and evidence is the kind of noun a checker could pursue. The
    # clause-final requirement keeps this UNRESOLVED.
    a = weigh_claim(Claim(text="this is the best evidence we have",
                          kind=ASSERTION))
    assert a.verdict == UNRESOLVED, a.note


def t_detect_rhetoric_names_its_reason():
    is_rhet, note = detect_rhetoric("She was pathetic")
    assert is_rhet and "was pathetic" in note, note
    is_rhet, note = detect_rhetoric("a bare claim")
    assert not is_rhet, note
    # When in doubt the detector stays silent: the False branch
    # always says why, so the silence is auditable.
    assert note, "the negative verdict must still narrate itself"


if __name__ == "__main__":
    for name, fn in sorted([(k, v) for k, v in globals().items()
                            if k.startswith("t_")]):
        check(name, fn)
    print(f"\n{PASS} gate tests passed.")
