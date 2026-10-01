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
UNRESOLVED -- unless it offers no checkable content at all (pure
evaluation, insult, puffery), in which case it is filed as RHETORIC:
noise, never judged, never a conviction. The cardinal rule holds
throughout: lack of proof is never scored as proof of falsehood.

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

from .alethic import FALSEHOOD, RHETORIC, TRVVTH, UNRESOLVED

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


# ---------------------------------------------------------------- rhetoric
# "A fool hath no delight in understanding, but that his heart may
#  discover itself." -- Proverbs 18:2 (KJV)
#
# The verse is the whole design brief: understanding is checkable
# content; the heart discovering itself is expression without any.
# The gate learned, on the night of 2026-10-01, that UNRESOLVED was
# carrying two different cargoes -- "checkable but unchecked" and
# "not even a claim" -- and that honesty required a second drawer.
# RHETORIC is that drawer. What follows is deliberately, even
# stubbornly, conservative: these patterns file a claim as noise
# only when no checkable content is offered anywhere in the text.
# When in doubt the detector stays silent and the claim keeps its
# UNRESOLVED -- the gate would rather mark noise as "not shown"
# than risk filing a real claim as noise. A detector that
# over-reaches becomes a censor; a detector that under-reaches is
# merely incomplete, and incompleteness is honest.

# The copulae: forms of "to be" that join a subject to its evaluation.
_RHETORIC_COPULAE = r"(?:is|are|was|were|am|be|been|being)"

# Pure evaluations: gradable adjectives with no truth conditions.
# Annihilating ("nothing"), insulting ("pathetic"), laudatory
# ("amazing") -- all alike uncheckable. What they share is not tone
# but the absence of anything a second observer could verify.
_RHETORIC_EVALS = (
    "nothing", "worthless", "pointless", "meaningless",
    "stupid", "idiotic", "pathetic", "terrible", "awful", "horrible",
    "disgusting", "vile", "incompetent", "useless", "lame",
    "best", "worst", "greatest",
    "amazing", "incredible", "perfect", "wonderful", "fantastic",
    "beautiful", "great",
)

# Evaluative nouns: "is an idiot", "is a genius". The article is
# optional in the pattern because usage varies ("is genius" is
# heard, and still offers nothing checkable).
_RHETORIC_NOUNS = (
    "idiot", "moron", "imbecile", "fraud", "clown", "loser",
    "disgrace", "joke", "failure",
    "genius", "hero", "legend",
)

# One rhetoric predicate: copula + optional article + evaluation,
# where the evaluation ENDS its clause. The clause-final lookahead
# is the conservative heart of the detector: "is the best evidence
# we have" does NOT match, because "evidence" follows "best" and
# evidence is the kind of noun a checker could pursue. Only when
# nothing checkable follows the evaluation -- punctuation or the
# end of the text -- does the predicate count.
_RHETORIC_PREDICATE = re.compile(
    r"\b" + _RHETORIC_COPULAE + r"\s+"
    r"(?:(?:a|an|the)\s+)?"
    r"(?:" + "|".join(_RHETORIC_EVALS + _RHETORIC_NOUNS) + r")"
    r"(?=\s*[.!?;:,]\s*|\s*$)",
    re.IGNORECASE,
)

# Checkable-content vetoes: if ANY of these appear in the text, the
# detector stands down, no matter what the predicates say. Each veto
# names something a checker could pursue: numbers anchor quantity,
# links point at sources, quoted spans are quotable against their
# source, citation shapes invoke authorities, and a year anchors
# the claim in time. A single checkable thread means the text might
# be a claim; the gate will not file a might-be-claim as noise.
_CHECKABLE_VETOES = (
    re.compile(r"\d"),                              # numbers
    re.compile(r"https?://|www\.", re.IGNORECASE),  # links
    re.compile(r"[\"'“”‘’].{1,}[\"'“”‘’]"),         # quoted material
    re.compile(r"§|\bv\.\s|\bU\.S\.C\.|\bU\.S\.\b"),  # citation shapes
    re.compile(r"\b(19|20)\d{2}\b"),                 # a year: anchored in time
)

# Negations: "is not stupid" is a denial, not an evaluation -- it
# belongs to whoever would defend the subject, and the gate files
# defenses as UNRESOLVED (awaiting grounds), never as noise.
_NEGATIONS = re.compile(r"\b(not|n't|never|no)\b", re.IGNORECASE)


def detect_rhetoric(text: str) -> tuple[bool, str]:
    """Decide whether an assertion offers no checkable content at all.

        "A fool hath no delight in understanding, but that his heart
         may discover itself." -- Proverbs 18:2 (KJV)

    Hypothesis
    ----------
    Some utterances shaped like claims are not claims: pure
    evaluation ("is nothing"), insult ("is an idiot"), and puffery
    ("is the best") carry no checkable content -- no number, no
    quotation, no citation, no verifiable predicate -- so there is
    nothing to prove and nothing to disprove. Filing such noise as
    UNRESOLVED ("not shown") is honest but imprecise: it lumps "the
    checker has not looked yet" with "there is nothing to look at."

    Method
    ------
    Two gates, in order, both conservative:

    1. Veto scan: if the text contains ANY checkable thread --
       digits, a link, quoted material, citation shapes, a year --
       return False at once. One thread is enough; the gate will
       not file a might-be-claim as noise.
    2. Predicate scan: find copula + evaluation constructions
       ("is nothing", "are idiots", "was the best") where the
       evaluation ends its clause. Skip any predicate whose clause
       carries a negation ("is not stupid" is a denial, not an
       evaluation). If at least one un-negated predicate survives,
       return True.

    Observation
    -----------
    "Johnathan Monroe is nothing" -> True ("is nothing", no vetoes).
    "an unproven thing" -> False (no predicate at all). "The answer
    is 42" -> False (digit veto). "He is not stupid" -> False (the
    negation breaks the copula-predicate shape; denials are not
    evaluations). "x", "maybe", "a bare claim" -> False (no predicate).

    Result
    ------
    (True, reason) names the predicate found; (False, reason) names
    why not -- a veto fired, a negation guarded, or no predicate
    appeared. The function never judges truth, character, or worth:
    True means "no checkable content offered," nothing more. Its
    known weaknesses are documented here and in the project notes:
    English-only, copula-centric, finite word lists, blind to
    sarcasm. The gate documents its own limits -- a detector that
    cannot name its blindness is a different kind of fool than the
    verse describes.
    """
    vetoes = (
        ("digits", _CHECKABLE_VETOES[0]),
        ("a link", _CHECKABLE_VETOES[1]),
        ("quoted material", _CHECKABLE_VETOES[2]),
        ("citation-shaped content", _CHECKABLE_VETOES[3]),
        ("a year", _CHECKABLE_VETOES[4]),
    )
    for name, pattern in vetoes:
        if pattern.search(text):
            return False, (
                f"not rhetoric: text contains {name}, which a checker "
                f"could pursue")
    # The citation-format patterns are anchored full-match shapes;
    # search them loosely here -- any citation-shaped span vetoes.
    if any(p.search(text) for p in _CITE_PATTERNS):
        return False, ("not rhetoric: text contains citation-shaped "
                       "content, which a checker could pursue")
    for match in _RHETORIC_PREDICATE.finditer(text):
        # The clause is whatever precedes the predicate back to the
        # previous clause boundary; a negation anywhere in it turns
        # the evaluation into a denial, and denials are not noise.
        clause_start = max(text.rfind(".", 0, match.start()),
                           text.rfind("!", 0, match.start()),
                           text.rfind("?", 0, match.start()),
                           text.rfind(";", 0, match.start())) + 1
        if _NEGATIONS.search(text[clause_start:match.start()]):
            continue
        predicate = match.group(0).strip()
        return True, (
            f"pure evaluation with no checkable content: {predicate!r} "
            f"-- no numbers, quotes, citations, or verifiable predicates "
            f"offered anywhere in the text")
    return False, "not rhetoric: no evaluative predicate found"


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
    verdict: str  # TRVVTH | UNRESOLVED | RHETORIC | FALSEHOOD
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
    """Weigh one claim on the TRVVTH axis. Never trusts; always checks.

    Hypothesis
    ----------
    A claim's kind determines what "checking" means: verbatim
    presence for quotes, recomputation for numbers, format for
    citations, and -- for assertions, which carry no proof machinery
    -- a prior question: is there anything here TO check?

    Method
    ------
    Quotes are TRVVTH iff verbatim in the supplied source. Numbers
    are TRVVTH iff the recomputation reproduces the expected value.
    Citations are never TRVVTH from format alone. Assertions first
    pass through detect_rhetoric: pure evaluation with no checkable
    content is filed as RHETORIC (noise, never judged); everything
    else without proof is UNRESOLVED (honest "not shown").

    Observation
    -----------
    The cardinal rule holds at every branch: lack of proof is never
    scored as proof of falsehood. RHETORIC is not a conviction --
    the gate files the noise; it does not judge the speaker.

    Result
    ------
    An Assessment with the verdict the checking earned, and a note
    narrating why, so the weighing stays auditable.
    """
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

    # ASSERTION: two honest outcomes, in order.
    #
    # First, the rhetoric screen: if the text is pure evaluation
    # with no checkable content anywhere in it -- "is nothing",
    # "is an idiot", "is the best" -- there is nothing to prove
    # and nothing to disprove, so UNRESOLVED ("not shown") would
    # be the wrong drawer. The gate files it as RHETORIC: noise,
    # never judged, never a conviction. This is a filing decision,
    # not a character judgment; the note says so explicitly.
    #
    # Otherwise, the gate has nothing checkable: honest "not shown".
    # Note the asymmetry is deliberate -- detect_rhetoric is
    # conservative by construction (any checkable thread vetoes),
    # so a claim that merely MIGHT be checkable keeps UNRESOLVED.
    is_rhetoric, rhetoric_note = detect_rhetoric(claim.text)
    if is_rhetoric:
        return Assessment(claim, RHETORIC, rhetoric_note)
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
