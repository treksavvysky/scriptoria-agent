#!/usr/bin/env python
"""
Quick smoke test for Scriptoria's /files/move endpoint.

Usage:
    python scriptoria_move_test.py a.txt b.txt
"""
import sys
import httpx


BASE = "http://localhost:8000"

def move_file(src: str, dest: str) -> None:
    resp = httpx.post(f"{BASE}/files/move", json={"src": src, "dest": dest})
    resp.raise_for_status()
    print(f"Move OK  →  {src}  →  {dest}")

def assert_exists(path: str, expect_200: bool) -> None:
    r = httpx.get(f"{BASE}/files/{path}")
    if expect_200:
        assert r.status_code == 200, f"{path} should exist but got {r.status_code}"
        print(f"✓ {path} exists")
    else:
        assert r.status_code == 404, f"{path} should NOT exist but got {r.status_code}"
        print(f"✓ {path} is gone (404)")

if __name__ == "__main__":
    try:
        src, dest = sys.argv[1:3]
    except ValueError:
        sys.exit("Need exactly two args: src dest")

    move_file(src, dest)
    assert_exists(dest, True)
    assert_exists(src, False)
    print("All checks passed ✔")
