#!/usr/bin/env python3
"""Probe RFCOMM channels on the OPPO Enco Buds to find the vendor serial channel."""
import socket

ADDR = "6C:0D:E1:5F:DB:4D"


def probe(channel: int) -> bool:
    s = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
    s.settimeout(2.5)
    try:
        s.connect((ADDR, channel))
        return True
    except Exception as exc:  # noqa: BLE001
        return f"{type(exc).__name__}: {exc}"  # type: ignore[return-value]
    finally:
        s.close()


for ch in range(1, 31):
    res = probe(ch)
    if res is True:
        print(f"[OPEN] RFCOMM channel {ch}")
    else:
        print(f"[    ] ch {ch:>2}  {res}")
