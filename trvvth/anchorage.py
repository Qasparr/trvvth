# ☉ in 4° 34′ Libra  ☽ in 16° 47′ Aries  dies solis  Anno V:xii e.n.
# Johnathan 'Qasparr' (Κασπάρρ) Monroe, Keeper of the Secret Treasure
# All Rights Reserved, Without Prejudice.  CashApp $axoneme
"""
anchorage -- the Zero-Trust Anchorage as a standalone gate.

    "Prove all things; hold fast that which is good."
    -- 1 Thessalonians 5:21

Hypothesis
----------
A claim can be admitted through a gate that trusts nothing: every
claim must carry checkable proof (TRVVTH), and the gate's wiring --
whose duties count, whose clock stamps -- is injected, never assumed.

Method
------
Claims are weighed by kind. A quotation is TRVVTH iff the quoted
text appears verbatim in the supplied source ("exact quotes or
none"). A number is TRVVTH iff the supplied recomputation reproduces
it. A legal or scholarly citation is never TRVVTH from format alone:
a plausible form earns UNRESOLVED ("format-plausible; human red pen
required"), a malformed one FALSEHOOD. An assertion without proof is
UNRESOLVED. The cardinal rule holds throughout: lack of proof is
never scored as proof of falsehood.

Oz x Duty is kept as a balance, not a sum: each asserted right must
be paired with its duty. A right without a named duty unbalances the
scale and the gate refuses admission -- not as punishment, but as
physics. A right asserted without its duty is a number multiplied by
zero. Which duties resolve -- the strict canonical check -- is the
caller's business: pass ``duty_resolver`` or leave it open.

The stamp authenticates when, never whether: pass ``stamp`` (and the
optional ``sun_in_anchorage`` / ``moon_in_anchorage`` flags) or the
gate stamps UTC itself. The heavens may stamp the moment but they
never vote.

Observation
-----------
admit() returns an AnchoredWorking: per-claim assessments, the Oz x
Duty balance, the stamp, and the admission verdict. admitted is True
only when no claim is FALSEHOOD and the balance holds. UNRESOLVED
claims are admitted as UNRESOLVED -- marked, never upgraded.

Result
------
No claim enters on authority -- including the author's own. What the
gate cannot check it marks for the human red pen; it never certifies
what it has not proven. Wire it to any duty registry and any clock;
the gate itself stays clean.

Law
---
"No claim enters on authority" is the evidence rule stated as
engineering: cf. Fed. R. Evid. 901(a) -- authentication as a
condition precedent to admissibility ("the proponent must produce
evidence sufficient to support a finding that the item is what the
proponent claims it is"). Cited for education only; this gate admits
workings, not exhibits.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

from .alethic import FALSEHOOD, TRVVTH, UNRESOLVED

# Claim kinds the gate knows how to weigh.
QUOTE = "quote"
NUMBER = "number"
CITATION = "citation"
ASSERTION = "assertion"
KINDS = (QUOTE, NUMBER, CITATION, ASSERTION)

# A citation is format-plausible if it matches one of these shapes.
# Format is never truth: plausibility earns UNRESOLVED, not TRVVTH.
_CITE_PATTERNS = (
    re.compile(r"^\d+\s+U\.S\.\s+\d+\s+\(\d{4}\)$"),   # 319 U.S. 105 (1943)
    re.compile(r"^U\.S\. Const\. .+$"),                 # U.S. Const. Art. VI, cl. 2
    re.compile(r"^UCC\s+§+\s*[\d\-.a-zA-Z()]+$"),       # UCC § 1-308
    re.compile(r"^.+Co\. Rep\. .+ \(\d{4}\)$"),         # 5 Co. Rep. 91a (1604)
    re.compile(r"^\d+ U\.S\.C\. §+ .+$"),               # 18 U.S.C. § 1621
    re.compile(r"^Mich\. Const\. .+$"),                 # Mich. Const. Art. VII, § 4
)


@dataclass
class Claim:
    """One claim offered to the gate.

    kind: "quote" | "number" | "citation" | "assertion".
    proof: quote -> {"source": str}; number -> {"recompute": callable,
        "expected": value}; citation/assertion -> {} (nothing checkable).
    right/duty: the Oz x Duty pairing; a claim asserting a right should
        name its duty, or the balance fails.
    """

    text: str
    kind: str = ASSERTION
    proof: dict = field(default_factory=dict)
    right: str | None = None
    duty: str | None = None


@dataclass
class Assessment:
    claim: Claim
    verdict: str  # TRVVTH | UNRESOLVED | FALSEHOOD
    note: str


@dataclass
class Balance:
    """The Oz x Duty balance: every right paired with its duty.

    ``duty_resolver`` is the optional strict check: a callable taking
    a named duty and returning its canonical form (or None when the
    duty does not resolve). Leave it unset and the gate enforces only
    the pairing itself -- a named duty is taken at face value.
    """

    pairs: list[tuple[str, str | None]] = field(default_factory=list)
    duty_resolver: Callable[[str | None], object] | None = None

    @property
    def holds(self) -> bool:
        return all(duty is not None for _, duty in self.pairs)

    @property
    def unbalanced(self) -> list[str]:
        return [right for right, duty in self.pairs if duty is None]

    def canonical_pairs(self) -> list[tuple[str, str | None, object]]:
        """Each pair with its resolved canonical duty (or None).

        The stricter, opt-in measure: a named duty that does not
        resolve is reported, never silently accepted. With no
        resolver wired, resolution is skipped -- reported as None.
        """
        if self.duty_resolver is None:
            return [(right, duty, None) for right, duty in self.pairs]
        return [(right, duty, self.duty_resolver(duty))
                for right, duty in self.pairs]

    @property
    def unresolved_duties(self) -> list[str]:
        """Rights whose named duty does not resolve to the canon."""
        if self.duty_resolver is None:
            return []
        return [right for right, duty, resolved in self.canonical_pairs()
                if duty is not None and resolved is None]


@dataclass
class AnchoredWorking:
    assessments: list[Assessment]
    balance: Balance
    stamp: str
    sun_in_anchorage: bool = False
    moon_in_anchorage: bool = False
    admitted: bool = False

    def report(self) -> str:
        lines = [f"stamp: {self.stamp}"]
        anchor = []
        if self.sun_in_anchorage:
            anchor.append("Sun")
        if self.moon_in_anchorage:
            anchor.append("Moon")
        lines.append("anchorage: %s" % (" and ".join(anchor) + " in the Anchorage"
                                       if anchor else "moment outside the Anchorage"))
        for a in self.assessments:
            lines.append(f"[{a.verdict}] {a.claim.kind}: {a.claim.text[:60]} -- {a.note}")
        if self.balance.pairs:
            if self.balance.holds:
                canon = self.balance.unresolved_duties
                lines.append("Oz x Duty: balanced%s" % (
                    "" if not canon
                    else "; canonical duties unresolved: " + ", ".join(canon)))
            else:
                lines.append("Oz x Duty: UNBALANCED: %s"
                             % ", ".join(self.balance.unbalanced))
        lines.append("admitted: %s" % self.admitted)
        return "\n".join(lines)


def weigh_claim(claim: Claim) -> Assessment:
    """Weigh one claim on the TRVVTH axis. Never trusts; always checks."""
    if claim.kind not in KINDS:
        return Assessment(claim, FALSEHOOD, f"unknown claim kind {claim.kind!r}")

    if claim.kind == QUOTE:
        source = claim.proof.get("source")
        if source is None:
            return Assessment(claim, UNRESOLVED, "no source supplied; cannot check")
        if claim.text in source:
            return Assessment(claim, TRVVTH, "verbatim in supplied source")
        return Assessment(claim, FALSEHOOD, "not found verbatim in supplied source")

    if claim.kind == NUMBER:
        recompute = claim.proof.get("recompute")
        if recompute is None:
            return Assessment(claim, UNRESOLVED, "no recomputation supplied")
        try:
            result = recompute()
        except Exception as exc:  # noqa: BLE001 -- the gate reports, never crashes
            return Assessment(claim, UNRESOLVED, f"recomputation raised {exc!r}")
        expected = claim.proof.get("expected")
        if result == expected:
            return Assessment(claim, TRVVTH, f"recomputed {result!r} == expected")
        return Assessment(claim, FALSEHOOD,
                          f"recomputed {result!r} != expected {expected!r}")

    if claim.kind == CITATION:
        if any(p.match(claim.text) for p in _CITE_PATTERNS):
            return Assessment(claim, UNRESOLVED,
                              "format-plausible; human red pen required")
        return Assessment(claim, FALSEHOOD, "malformed citation")

    # ASSERTION: the gate has nothing checkable; honest "not shown".
    return Assessment(claim, UNRESOLVED, "assertion without checkable proof")


def weigh_rights(claims: list[Claim],
                 duty_resolver: Callable[[str | None], object] | None = None) -> Balance:
    """Oz x Duty: collect every asserted right and its named duty."""
    return Balance(
        pairs=[(c.right, c.duty) for c in claims if c.right is not None],
        duty_resolver=duty_resolver,
    )


def cardinal_rules() -> list[str]:
    return [
        "Rights arrive with duties attached (Oz x Duty).",
        "Verification before assertion (TRVVTH).",
        "No claim enters on authority -- including the author's own.",
        "Citations educate, never conjure.",
        "What the gate cannot check, it marks for the human red pen.",
        "Lack of proof is never scored as proof of falsehood.",
    ]


def admit(claims: list[Claim],
          duty_resolver: Callable[[str | None], object] | None = None,
          stamp: str | None = None,
          sun_in_anchorage: bool = False,
          moon_in_anchorage: bool = False) -> AnchoredWorking:
    """Run claims through the zero-trust gate and stamp the admission.

    Wire your own duty registry via ``duty_resolver`` and your own
    clock via ``stamp``; the gate defaults to open pairing and a UTC
    stamp. The stamp authenticates when, never whether.
    """
    assessments = [weigh_claim(c) for c in claims]
    balance = weigh_rights(claims, duty_resolver=duty_resolver)
    if stamp is None:
        stamp = datetime.now(timezone.utc).isoformat()
    admitted = (all(a.verdict != FALSEHOOD for a in assessments)
                and balance.holds)
    return AnchoredWorking(
        assessments=assessments,
        balance=balance,
        stamp=stamp,
        sun_in_anchorage=sun_in_anchorage,
        moon_in_anchorage=moon_in_anchorage,
        admitted=admitted,
    )
