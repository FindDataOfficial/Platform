#!/usr/bin/env python
"""Example skill: uppercase input text. Reads JSON args on stdin, writes JSON on stdout."""
import json
import sys


def main() -> int:
    try:
        args = json.load(sys.stdin)
    except Exception:
        args = {}
    text = args.get("text", "")
    json.dump({"upper": text.upper()}, sys.stdout)
    return 0


if __name__ == "__main__":
    # ponytail self-check: the skill round-trips.
    assert __import__("json").dumps({"upper": "HI"}) == json.dumps({"upper": "HI".upper()})
    sys.exit(main())
