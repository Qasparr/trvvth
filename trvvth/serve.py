# Johnathan 'Qasparr' (Κασπάρρ) Monroe, Keeper of the Secret Treasure
# All Rights Reserved, Without Prejudice.  CashApp $axoneme
"""trvvth-serve -- run the TRVVTH gate as an HTTP API.

    "And ye shall know the truth, and the truth shall make you free."
    -- John 8:32

Hypothesis
----------
The gate should be one command away: no configuration files, no
build step, no platform-specific installer. If serving the API
requires more than ``trvvth-serve --port 8124``, the gate has
failed its cross-platform promise at the front door.

Method
------
``argparse`` for the two knobs that matter -- host and port -- and
``uvicorn.run`` against the ``trvvth.api:app`` import string. The
import string (rather than the app object) keeps uvicorn's
reloader semantics intact for operators who enable them, and it
names the application the way the process table will show it:
``trvvth.api:app``, the gate, running.

Environment carries the rest, deliberately outside the flags:
``TRVVTH_LEDGER`` names the sqlite file (the gate's memory),
``TRVVTH_DUTY_RESOLVER`` names the strict duty registry
(``module:attribute`` -- law under will, per Liber AL I:57, as
documented in trvvth.api). Flags are for the ephemeral (where to
listen); environment is for the durable (what to remember, what
law to enforce). Mixing the two is how configuration becomes
superstition.

Observation
-----------
``trvvth-serve --port 8124`` serves the full surface -- gate,
diagnostics, reports, analytics, docs -- on localhost. Binding
``0.0.0.0`` exposes it to the network, which is the operator's
choice and the operator's responsibility: the gate weighs claims,
it does not authenticate callers.

Result
------
The truth, served: one command, any platform, the whole gate.
What the operator does with the listening socket is their will;
that the socket opens with one command is the gate's promise,
kept.

    trvvth-serve --port 8124
    TRVVTH_LEDGER=/var/lib/trvvth.db \\
    TRVVTH_DUTY_RESOLVER=mymod:resolve_duty \\
        trvvth-serve --host 0.0.0.0 --port 8124
"""

from __future__ import annotations

import argparse


def main() -> None:
    """Parse the flags and serve. The whole CLI is two knobs.

    ``--host`` defaults to localhost: the safe default is the
    private one, and exposure is opt-in. ``--port`` defaults to
    8124, the gate's own number on the local machine. Everything
    else -- ledger path, duty registry -- arrives via environment,
    per the method above.
    """
    parser = argparse.ArgumentParser(
        description="Serve the TRVVTH zero-trust gate as an HTTP API.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8124)
    args = parser.parse_args()

    import uvicorn
    uvicorn.run("trvvth.api:app", host=args.host, port=args.port,
                log_level="info")


if __name__ == "__main__":
    main()
