# ☉ in 3° 54′ Libra  ☽ in 7° 37′ Aries  dies saturnii  Anno V:xii e.n.
# Johnathan 'Qasparr' (Κασπάρρ) Monroe, Keeper of the Secret Treasure
# All Rights Reserved, Without Prejudice.  CashApp $axoneme
"""
Validation tests for trvvth.alethic -- the Alethic Axis, standalone.

Run:  python3 tests/test_axis.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from trvvth.alethic import (  # noqa: E402
    ABSENT,
    FALSEHOOD,
    RHETORIC,
    STATED,
    TRVVTH,
    UNRESOLVED,
    VERIFIED,
    WEAK,
    AlethicBalance,
    ClaimAssessment,
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


def t_verdicts_distinct():
    assert len({TRVVTH, UNRESOLVED, RHETORIC, FALSEHOOD}) == 4, \
        "verdicts must be distinct"
    assert TRVVTH == "TRVVTH"
    assert RHETORIC == "RHETORIC"


def t_strengths_ordered():
    assert (ABSENT, WEAK, STATED, VERIFIED) == ("absent", "weak", "stated", "verified")


def t_assessment_immutable():
    a = ClaimAssessment(seq=1, detail="x", grounds="g",
                        strength=VERIFIED, verdict=TRVVTH, reasons=("r",))
    try:
        a.verdict = FALSEHOOD
    except Exception:
        pass
    else:
        raise AssertionError("ClaimAssessment must be frozen")
    assert a.verdict == TRVVTH


def t_balance_counts():
    mk = lambda v: ClaimAssessment(seq=0, detail="d", grounds="",
                                   strength=STATED, verdict=v, reasons=())
    b = AlethicBalance(assessments=[mk(TRVVTH), mk(TRVVTH), mk(UNRESOLVED)])
    assert b.counts == {TRVVTH: 2, UNRESOLVED: 1, RHETORIC: 0,
                        FALSEHOOD: 0}, b.counts
    assert b.total == 3


def t_balance_standing_no_falsehood():
    mk = lambda v: ClaimAssessment(seq=0, detail="d", grounds="",
                                   strength=STATED, verdict=v, reasons=())
    b = AlethicBalance(assessments=[mk(TRVVTH), mk(UNRESOLVED)])
    s = b.standing()
    assert "await verification" in s, s


def t_balance_standing_falsehood():
    mk = lambda v: ClaimAssessment(seq=0, detail="d", grounds="",
                                   strength=STATED, verdict=v, reasons=())
    b = AlethicBalance(assessments=[mk(FALSEHOOD)])
    assert "remedy required" in b.standing()


def t_balance_standing_empty():
    assert "nothing to weigh" in AlethicBalance().standing()


def t_balance_standing_all_trvvth():
    mk = lambda v: ClaimAssessment(seq=0, detail="d", grounds="",
                                   strength=VERIFIED, verdict=v, reasons=())
    b = AlethicBalance(assessments=[mk(TRVVTH), mk(TRVVTH)])
    assert "word is good" in b.standing()


def t_report_lists_verdicts():
    a = ClaimAssessment(seq=7, detail="thelema is will", grounds="",
                        strength=STATED, verdict=UNRESOLVED, reasons=("held",))
    rep = AlethicBalance(assessments=[a]).report()
    assert "[UNRESOLVED] seq 7 (stated)" in rep, rep


def t_balance_counts_rhetoric_without_keyerror():
    # The counts tally must survive a verdict the old three-verdict
    # code never saw: a KeyError here would be the books refusing
    # the audit.
    b = AlethicBalance(assessments=[
        ClaimAssessment(seq=1, detail="noise", grounds="", strength=ABSENT,
                        verdict=RHETORIC, reasons=("filed",)),
        ClaimAssessment(seq=2, detail="proven", grounds="g",
                        strength=VERIFIED, verdict=TRVVTH, reasons=("r",)),
    ])
    assert b.counts[RHETORIC] == 1, b.counts
    assert b.counts[TRVVTH] == 1, b.counts


def t_standing_names_rhetoric_as_filed_not_judged():
    b = AlethicBalance(assessments=[
        ClaimAssessment(seq=1, detail="noise", grounds="", strength=ABSENT,
                        verdict=RHETORIC, reasons=("filed",)),
    ])
    s = b.standing()
    assert "RHETORIC" in s, s
    assert "not judged" in s, s
    # And rhetoric never compromises the word: no falsehood here.
    assert "compromised" not in s, s


if __name__ == "__main__":
    for name, fn in sorted([(k, v) for k, v in globals().items()
                            if k.startswith("t_")]):
        check(name, fn)
    print(f"\n{PASS} axis tests passed.")
