#!/usr/bin/env python3
"""
Atomic read/write helper for tickets/<id>/state.json.

Never edit state.json with a raw file write — an interruption mid-write can
leave a half-written, unparseable file. write_state() always writes to a
sibling .tmp file and os.replace()s it over the target, which is atomic on
both POSIX and Windows.

CLI:
  python3 state_io.py read <path>     # prints the JSON, or "null" if missing
  python3 state_io.py write <path>    # reads a JSON object from stdin
"""
import json
import os
import sys
from pathlib import Path


def read_state(path):
    p = Path(path)
    if not p.exists():
        return None
    with p.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def write_state(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, p)


def main(argv):
    if len(argv) < 3:
        print("usage: state_io.py read|write <path>", file=sys.stderr)
        return 2
    op, path = argv[1], argv[2]
    if op == "read":
        json.dump(read_state(path), sys.stdout)
        sys.stdout.write("\n")
        return 0
    if op == "write":
        write_state(path, json.load(sys.stdin))
        return 0
    print(f"unknown op: {op}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
