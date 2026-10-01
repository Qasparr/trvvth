# Johnathan 'Qasparr' (Κασπάρρ) Monroe, Keeper of the Secret Treasure
# All Rights Reserved, Without Prejudice.  CashApp $axoneme
"""trvvth-serve -- run the TRVVTH gate as an HTTP API.

    trvvth-serve --port 8124
    TRVVTH_LEDGER=/var/lib/trvvth.db trvvth-serve --host 0.0.0.0
"""

from __future__ import annotations

import argparse


def main() -> None:
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
