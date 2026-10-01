# ☉ in 3° 54′ Libra  ☽ in 7° 37′ Aries  dies saturnii  Anno V:xii e.n.
# Johnathan 'Qasparr' (Κασπάρρ) Monroe, Keeper of the Secret Treasure
# All Rights Reserved, Without Prejudice.  CashApp $axoneme
"""trvvth -- the Zero-Trust Anchorage and the Alethic Axis, standalone.

The gate any agent can use: claims in, verdicts out, no trust assumed.

    from trvvth import Claim, admit, TRVVTH

    working = admit([
        Claim(text="the sky is blue", kind="assertion"),
        Claim(text="2 + 2", kind="number",
              proof={"recompute": lambda: 2 + 2, "expected": 4}),
    ])
    print(working.report())
"""

__version__ = "0.2.2"

from .alethic import (  # noqa: F401
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
from .anchorage import (  # noqa: F401
    ASSERTION,
    CITATION,
    KINDS,
    NUMBER,
    QUOTE,
    AnchoredWorking,
    Assessment,
    Balance,
    Claim,
    admit,
    cardinal_rules,
    detect_rhetoric,
    weigh_claim,
    weigh_rights,
)
