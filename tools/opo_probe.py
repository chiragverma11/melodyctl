#!/usr/bin/env python3
"""Replay OPOv1 handshake + battery query over RFCOMM ch12 and dump responses."""
import socket
import time

ADDR = "6C:0D:E1:5F:DB:4D"
CH = 12

HELLO = bytes.fromhex("AA07000000012300 0012".replace(" ", ""))
REGISTER = bytes.fromhex("AA0C000000854105000 0B550A069".replace(" ", ""))
BATT_Q = bytes.fromhex("AA07000006012500 00".replace(" ", ""))


def drain(sock, wait: float) -> bytes:
    end = time.time() + wait
    buf = bytearray()
    sock.settimeout(0.3)
    while time.time() < end:
        try:
            chunk = sock.recv(256)
            if not chunk:
                break
            buf += chunk
            end = time.time() + 0.5  # extend while data keeps flowing
        except socket.timeout:
            continue
        except OSError:
            break
    return bytes(buf)


def show(tag: str, data: bytes) -> None:
    print(f"  {tag}: {data.hex(' ').upper()}" if data else f"  {tag}: (none)")


s = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
s.settimeout(10)
print(f"[*] connecting RFCOMM ch{CH} ...")
s.connect((ADDR, CH))
print("[+] connected")

try:
    print(f"[TX] HELLO    {HELLO.hex(' ').upper()}")
    s.sendall(HELLO)
    show("RX-hello", drain(s, 3))

    print(f"[TX] REGISTER {REGISTER.hex(' ').upper()}")
    s.sendall(REGISTER)
    show("RX-reg", drain(s, 3))

    print(f"[TX] BATT_Q   {BATT_Q.hex(' ').upper()}")
    s.sendall(BATT_Q)
    show("RX-batt", drain(s, 4))
finally:
    s.close()
    print("[*] closed")
