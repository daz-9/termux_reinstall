#!/usr/bin/env python3
"""Entry point: pick what to run. No imports from setup/configure."""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable  # the same python running this file

MENU = """
[1] Full install    (setup + configure)
[2] Setup only      (packages, font, repos)
[3] Configure only  (zsh, nvim, start-desktop.sh)
[4] Quit
"""


def run_script(name: str) -> int:
    """Run a sibling script by filename. Returns its exit code."""
    path = os.path.join(HERE, name)
    if not os.path.exists(path):
        print(f"[!] {name} not found next to main.py")
        return 1
    print(f"[*] Running {name} ...")
    return subprocess.run([PY, path]).returncode


def dispatch(choice: str) -> int:
    if choice in ("1", "all"):
        rc = run_script("setup.py")
        if rc != 0:
            print("[!] setup.py failed, skipping configure.")
            return rc
        return run_script("configure.py")

    if choice in ("2", "setup"):
        return run_script("setup.py")

    if choice in ("3", "configure"):
        return run_script("configure.py")

    if choice in ("4", "quit", "q"):
        print("Bye.")
        return 0

    print("[!] Invalid choice.")
    return 1


def main() -> int:
    # Flags for non-interactive use
    args = sys.argv[1:]
    if args:
        return dispatch(args[0].lstrip("-"))

    # No flags -> interactive
    print(MENU)
    try:
        choice = input("Choose [1-4]: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return 130
    return dispatch(choice)


if __name__ == "__main__":
    raise SystemExit(main())