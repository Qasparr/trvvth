# ☉ in 3° 54′ Libra  ☽ in 7° 37′ Aries  dies saturnii  Anno V:xii e.n.
# Johnathan 'Qasparr' (Κασπάρρ) Monroe, Keeper of the Secret Treasure
# All Rights Reserved, Without Prejudice.  CashApp $axoneme
"""
alethic -- the Alethic Axis as a standalone accounting.

    "And ye shall know the truth, and the truth shall make you free."
    -- John 8:32

Hypothesis
----------
TRVVTH is Good and Righteous; Falsehood or Deception is Evil -- and
the difference can be kept as an accounting, not merely professed.

Method
------
Every claim weighed receives a verdict on the axis, and the working
as a whole receives a balance -- the state of its word:

* TRVVTH -- the claim's grounds verify against the record.
* UNRESOLVED -- the claim is neither proven nor disproven. Weak
  grounds, authority-cited grounds, missing grounds: all land here.
* RHETORIC -- the claim offers no checkable content at all: pure
  evaluation, insult, or puffery. Filed as noise, never judged.
  RHETORIC is not a lesser FALSEHOOD and not a failed TRVVTH; it
  is the gate declining to weigh what was never a weighing-matter.
* FALSEHOOD -- the claim's grounds are fabricated, or the claim was
  retracted on the record.

Grounds strength (what "weighing" means): verified (checkable,
checked); stated (appeal to authority -- not verified, not
dishonest); weak (hedges); absent (no grounds recorded).

Observation
-----------
ClaimAssessment carries the weighing step by step in ``reasons``,
so the verdict is auditable -- the axis must show its work, or it
is mere assertion. AlethicBalance tallies the working's account.

Result
------
The cardinal rule, enforced structurally: a lack of proof is never
scored as proof of falsehood. An unproven claim is UNRESOLVED -- an
honest "not shown" -- not FALSEHOOD. Collapsing the two would let
the audit manufacture guilt, which is itself a form of falsehood.
The axis cuts both ways: it judges claims, and it judges the
judging.

Law
---
The law, too, treats falsehood as a wrong distinct from the merely
unproven: 18 U.S.C. Sec. 1621 punishes the false statement, not the
unsubstantiated one. The parallel is educational only -- this module
creates no legal effect; it keeps the working's own books.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# The four verdicts of the axis.
#
# TRVVTH, UNRESOLVED, FALSEHOOD are the original three: proven,
# not-shown, disproven. RHETORIC is the fourth, added when the gate
# learned the difference between "checkable but unchecked" and
# "not even a claim": pure evaluation, insult, or puffery carries
# no checkable content, so there is nothing to prove and nothing to
# disprove. The gate files it as noise -- it does not judge it.
# A verdict of RHETORIC says nothing about the speaker's character
# and nothing about the statement's truth; it says the statement
# never entered the jurisdiction of checking.
TRVVTH = "TRVVTH"
UNRESOLVED = "UNRESOLVED"
RHETORIC = "RHETORIC"
FALSEHOOD = "FALSEHOOD"

# Grounds strength, weakest to strongest.
ABSENT = "absent"
WEAK = "weak"
STATED = "stated"
VERIFIED = "verified"


@dataclass(frozen=True)
class ClaimAssessment:
    """One claim, weighed: its grounds, their strength, the verdict.

    ``reasons`` narrates the weighing step by step, so the verdict is
    auditable -- the axis must show its work, or it is mere assertion.
    """

    seq: int
    detail: str
    grounds: str
    strength: str  # absent | weak | stated | verified
    verdict: str  # TRVVTH | UNRESOLVED | RHETORIC | FALSEHOOD
    reasons: tuple


@dataclass
class AlethicBalance:
    """The working's account: how its word stands."""

    assessments: list[ClaimAssessment] = field(default_factory=list)

    @property
    def counts(self) -> dict[str, int]:
        # Every known verdict gets a counter up front -- including
        # RHETORIC -- so a verdict the gate can render never raises
        # KeyError here. The tally must be able to count whatever
        # the axis can say; a counter that crashes on a legal
        # verdict would be the books refusing the audit.
        tally = {TRVVTH: 0, UNRESOLVED: 0, RHETORIC: 0, FALSEHOOD: 0}
        for a in self.assessments:
            tally[a.verdict] += 1
        return tally

    @property
    def total(self) -> int:
        return len(self.assessments)

    def standing(self) -> str:
        """A plain sentence on the state of the working's word.

        RHETORIC assessments are reported as filed noise -- counted,
        never judged -- so the sentence distinguishes "awaiting
        verification" (UNRESOLVED, a debt the working still owes the
        record) from "filed as noise" (RHETORIC, no debt incurred,
        nothing owed). FALSEHOOD still compromises the word outright.
        """
        c = self.counts
        if self.total == 0:
            return "No claims on the record; the axis has nothing to weigh."
        if c[FALSEHOOD]:
            return (f"{c[FALSEHOOD]} claim(s) judged FALSEHOOD -- the "
                    f"working's word is compromised; remedy required.")
        rhetoric = (f", {c[RHETORIC]} filed as RHETORIC (noise, not judged)"
                    if c[RHETORIC] else "")
        if c[UNRESOLVED]:
            return (f"{c[TRVVTH]} TRVVTH, {c[UNRESOLVED]} UNRESOLVED, no "
                    f"falsehood -- the word stands, "
                    f"{c[UNRESOLVED]} claim(s) await verification"
                    f"{rhetoric}.")
        if c[RHETORIC]:
            return (f"{c[TRVVTH]} TRVVTH, no falsehood, "
                    f"{c[RHETORIC]} claim(s) filed as RHETORIC -- noise, "
                    f"not judged; the word stands.")
        return (f"All {c[TRVVTH]} claims TRVVTH -- the working's word "
                f"is good.")

    def report(self) -> str:
        lines = [f"Alethic balance: {self.counts}"]
        for a in self.assessments:
            lines.append(f"  [{a.verdict}] seq {a.seq} ({a.strength}): "
                         f"{a.detail[:60]}")
            for r in a.reasons:
                lines.append(f"      - {r}")
        lines.append(self.standing())
        return "\n".join(lines)
