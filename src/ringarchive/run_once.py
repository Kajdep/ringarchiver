"""
python -m ringarchive.run_once

Runs one archive pass against the Ring simulator / real API.
Reads credentials from .env or environment variables.
"""
from __future__ import annotations
import os, sys

# Load .env file if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

from .ring_client import RingClient
from .handler     import run_once

def main() -> None:
    print("=== RingArchive — single run ===")
    client = RingClient.from_env()
    result = run_once(client)
    print(f"\nResult: archived={result['archived']}  skipped={result['skipped']}  errors={result['errors']}")
    if result["ids"]:
        print("Archived event IDs:")
        for eid in result["ids"]:
            print(f"  {eid}")

if __name__ == "__main__":
    main()
