#!/data/data/com.termux/files/usr/bin/python3
"""Stream bspwm desktop & layout state as JSON lines for eww deflisten."""

import json
import os
import signal
import subprocess
import sys


def parse_report(line: str) -> dict | None:
    parts = line.strip().split(":")
    if len(parts) < 2:
        return None
    desktops = []
    layout = "T"
    for part in parts:
        if len(part) < 2:
            continue
        tag, name = part[0], part[1:]
        if tag in "FfOoUu":
            try:
                num = int(name)
            except ValueError:
                continue
            desktops.append({
                "num": num,
                "focused": tag in "FOU",
                "occupied": tag in "Oo",
                "urgent": tag in "Uu",
            })
        elif tag == "L":
            layout = name
    if not desktops:
        return None
    return {"layout": layout, "desktops": desktops}


def main() -> int:
    proc = subprocess.Popen(
        ["bspc", "subscribe", "report"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1,
    )

    def stop(_sig, _frame):
        proc.terminate()
        sys.exit(0)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    assert proc.stdout is not None
    for line in proc.stdout:
        state = parse_report(line)
        if state is not None:
            print(json.dumps(state), flush=True)
    return proc.wait()


if __name__ == "__main__":
    sys.exit(main())
