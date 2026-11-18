#!/data/data/com.termux/files/usr/bin/python3
"""Stream Termux/X11 CPU utilization across visible processes for Polybar."""

import os
import signal
import sys
import time


def _total_jiffies() -> int:
    total = 0
    for name in os.listdir("/proc"):
        if not name.isdigit():
            continue
        try:
            with open(f"/proc/{name}/stat") as f:
                data = f.read()
            rp = data.rfind(")")
            if rp < 0:
                continue
            fields = data[rp + 2:].split()
            total += int(fields[11]) + int(fields[12])
        except (OSError, IndexError, ValueError):
            pass
    return total


def main() -> int:
    running = True

    def stop(_signum, _frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    clk = os.sysconf("SC_CLK_TCK")
    ncpu = os.cpu_count() or 1
    j_prev = _total_jiffies()
    t_prev = time.monotonic()

    # Emit initial quick sample right away, then poll every 3s
    time.sleep(0.35)
    while running:
        j_now = _total_jiffies()
        t_now = time.monotonic()
        dt = max(0.05, t_now - t_prev)
        pct = min(100, max(0, round(((j_now - j_prev) / clk) / (dt * ncpu) * 100.0)))
        j_prev, t_prev = j_now, t_now

        if pct >= 80:
            color = "#f38ba8"
        elif pct >= 50:
            color = "#fab387"
        else:
            color = "#94e2d5"

        print(f"%{{F{color}}}%{{F-}} {pct}%", flush=True)
        for _ in range(30):
            if not running:
                break
            time.sleep(0.1)

    return 0


if __name__ == "__main__":
    sys.exit(main())
