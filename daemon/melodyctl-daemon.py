#!/usr/bin/env python3
"""melodyctl-daemon - poll HeyMelody-family earbud battery and publish it as JSON.

Writes $XDG_RUNTIME_DIR/melodyctl-battery.json atomically, e.g.:
  {"ts": 1760.., "left": 80, "right": 100, "case": 70, "addr": "6C:0D:E1:5F:DB:4D"}
Any UI (Quickshell/DMS widget, waybar, script) can read this file.
"""
from __future__ import annotations

import json
import os
import signal
import sys
import time

# speak to melodyctl.py in the repository root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from melodyctl import ADDR_DEFAULT, Buds  # noqa: E402

RUNTIME = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
OUT = os.path.join(RUNTIME, "melodyctl-battery.json")
INTERVAL = float(os.environ.get("MELODYCTL_INTERVAL")
                 or os.environ.get("ENCO_INTERVAL", "30"))
_running = True


def _stop(*_a):
    global _running
    _running = False


def publish(payload: dict) -> None:
    tmp = f"{OUT}.tmp"
    with open(tmp, "w") as fh:
        json.dump(payload, fh)
    os.replace(tmp, OUT)


def main() -> int:
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    print(f"[melodyctl-daemon] publishing to {OUT} every {INTERVAL}s", flush=True)
    while _running:
        started = time.time()
        try:
            with Buds(ADDR_DEFAULT, timeout=8.0) as conn:
                b = conn.battery()
            payload = {"ts": int(time.time()), "addr": ADDR_DEFAULT, **b}
            publish(payload)
            print(f"[melodyctl-daemon] {payload}", flush=True)
        except Exception as exc:  # noqa: BLE001
            publish({"ts": int(time.time()), "addr": ADDR_DEFAULT, "error": str(exc)})
            print(f"[melodyctl-daemon] ! {exc}", flush=True)
        # sleep the remainder of the interval, but stay responsive to signals
        while _running and (time.time() - started) < INTERVAL:
            time.sleep(0.25)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
