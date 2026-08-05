#!/usr/bin/env python3
"""
Intentionally crash the sample site to generate outage logs for testing.

Usage:
  python crash_trigger.py <kind> [--url BASE_URL]

  kind: one of db, memory, timeout, nullref, disk, random

Examples:
  python crash_trigger.py db
  python crash_trigger.py random --url http://localhost:5001
"""

import argparse
import random
import sys

import requests

KINDS = ["db", "memory", "timeout", "nullref", "disk"]


def main():
    parser = argparse.ArgumentParser(description="Trigger an intentional crash on the sample site.")
    parser.add_argument("kind", choices=KINDS + ["random"], help="type of crash to trigger")
    parser.add_argument("--url", default="http://localhost:5001", help="base URL of the sample site")
    args = parser.parse_args()

    kind = random.choice(KINDS) if args.kind == "random" else args.kind

    try:
        resp = requests.post(f"{args.url}/crash/{kind}", timeout=10)
    except requests.exceptions.ConnectionError:
        print(f"Could not reach {args.url}. Is the sample site running? (python app/app.py)")
        sys.exit(1)

    print(f"Triggered crash kind='{kind}' -> status {resp.status_code}")
    print(resp.json())


if __name__ == "__main__":
    main()
