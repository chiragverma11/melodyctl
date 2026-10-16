#!/usr/bin/env python3
"""Query several OPOv1 categories over RFCOMM ch12 and dump raw responses."""
import socket
import time

ADDR = "6C:0D:E1:5F:DB:4D"
CH = 12

HELLO = bytes.fromhex("AA07000000 01 23 000012".replace(" ", ""))

QUERIES = {
    "battery": bytes.fromhex("AA07000006012500 00".replace(" ", "")),
    "device_info": bytes.fromhex("AA07000003 0128 00 00".replace(" ", "")),
    "eq": bytes.fromhex("AA07000005 012B 00 00".replace(" ", "")),
    "anc_status": bytes.fromhex("AA0900 00 04 82 44 02 00 00 F2".replace(" ", "")),
}


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
            end = time.time() + 0.5
        except socket.timeout:
            continue
        except OSError:
            break
    return bytes(buf)


def parse_battery(data: bytes) -> str:
    # payload after the 2 pad bytes following SEQ: 0x00 0x00 <count> <id><val>...
    i = data.find(0x06)
    body = data[10:]  # count + pairs
    pairs = [(body[j], body[j + 1]) for j in range(1, len(body) - 1, 2)]
    names = {1: "left", 2: "right", 3: "case"}
    return ", ".join(f"{names.get(i, hex(i))}={v}%" for i, v in pairs)


s = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
s.settimeout(10)
s.connect((ADDR, CH))
print("[+] connected ch12")

s.sendall(HELLO)
print("HELLO   ->", drain(s, 2).hex(" ").upper())

for name, pkt in QUERIES.items():
    s.sendall(pkt)
    resp = drain(s, 3)
    print(f"\n{name:<12} TX {pkt.hex(' ').upper()}")
    print(f"{'':<12} RX {resp.hex(' ').upper()}")
    if name == "battery" and resp.startswith(b"\xAA"):
        print(f"{'':<12} -> {parse_battery(resp)}")

s.close()
print("\n[*] closed")
