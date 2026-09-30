![TRVVTH logo](assets/logo.webp)

# TRVVTH — the Zero-Trust Anchorage, standalone

The gate any agent can use. Claims in, verdicts out, no trust assumed.

> "Prove all things; hold fast that which is good." — 1 Thessalonians 5:21

## The idea

Every claim offered to the gate is weighed by kind:

| kind | TRVVTH iff | else |
|---|---|---|
| `quote` | text appears **verbatim** in the supplied source | FALSEHOOD (or UNRESOLVED if no source given) |
| `number` | the supplied recomputation reproduces it | FALSEHOOD on mismatch, UNRESOLVED on no recomputation |
| `citation` | — | UNRESOLVED if format-plausible ("human red pen required"), FALSEHOOD if malformed |
| `assertion` | — | UNRESOLVED ("assertion without checkable proof") |

The cardinal rule holds throughout: **lack of proof is never scored as proof of falsehood.**

Oz × Duty is kept as a balance: every asserted right must name its duty, or admission is refused. Which duties count as canonical is the caller's business — inject a `duty_resolver`, or leave the pairing open.

## Use

```python
from trvvth import Claim, admit, TRVVTH

working = admit([
    Claim(text="thelema is 93", kind="number",
          proof={"recompute": lambda: 20 + 5 + 30 + 8 + 40 + 1, "expected": 93}),
    Claim(text="my colour is black to the blind", kind="quote",
          proof={"source": open("liber-al.txt").read()}),
    Claim(text="I have a right to speak", kind="assertion",
          right="speech", duty="to speak truly"),
])

print(working.report())
print(working.admitted)   # True only if no FALSEHOOD and the balance holds
```

Wire your own registry and clock:

```python
working = admit(
    claims,
    duty_resolver=my_duty_registry.resolve,  # strict canonical check
    stamp=my_clock.now(),                     # the stamp says when, never whether
)
```

## The axis

`trvvth.alethic` carries the Alethic Axis as an accounting: `TRVVTH` /
`UNRESOLVED` / `FALSEHOOD` verdicts, grounds strengths (`verified`,
`stated`, `weak`, `absent`), `ClaimAssessment`, and `AlethicBalance`
— the working's account of how its word stands.

## Provenance

Extracted from PERSONA V (Johnathan 'Κασπάρρ' Monroe, Keeper of the
Secret Treasure) so the gate stands alone: any agent — any framework,
any model — can import the gate without importing the persona.

All Rights Reserved, Without Prejudice.
