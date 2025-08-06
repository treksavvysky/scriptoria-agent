#!/usr/bin/env python
"""
Quick smoke test for Scriptoria's /move-file endpoint.

Usage:
    python scriptoria_move_test.py a.txt b.txt
"""
import os
import pathlib
import sys
import httpx


BASE = "http://localhost:8000"
WORKSPACE = pathlib.Path(os.getenv("SCRIPTORIA_WORKSPACE", "/tmp/scriptoria_workspace"))

def move_file(src: str, dest: str) -> None:
    resp = httpx.post(f"{BASE}/move-file", json={"source_path": src, "destination_path": dest})
    resp.raise_for_status()
    print(f"Move OK  →  {src}  →  {dest}")


def assert_exists(path: str, should_exist: bool) -> None:
    abs_path = WORKSPACE / path
    exists = abs_path.exists()
    if should_exist:
        assert exists, f"{path} should exist but does not"
        print(f"✓ {path} exists")
    else:
        assert not exists, f"{path} should NOT exist but does"
        print(f"✓ {path} is gone")

if __name__ == "__main__":
    try:
        src, dest = sys.argv[1:3]
    except ValueError:
        sys.exit("Need exactly two args: src dest")

    move_file(src, dest)
    assert_exists(dest, True)
    assert_exists(src, False)
    print("All checks passed ✔")
