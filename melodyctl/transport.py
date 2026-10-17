"""Transport layer: RFCOMM session (address, channel, connect, hello, send/receive)."""
from __future__ import annotations

import os
import socket
import time

from .errors import MelodyctlError
from .protocol import CMD_BATT_GET, CMD_CAPS, CMD_EQ_SET, CMD_GAMESOUND_SET, CMD_GESTURES_GET, CMD_GESTURES_SET, CMD_HELLO, CMD_NOTIFY_REG, CMD_NOTIFY_SUB, CMD_SWITCH_FEATURE, CMD_VERSION_GET, COMPONENT, FEATURE_GAME_MODE, RESP_FLAG, decode_caps, decode_gestures, decode_version_records, frame, parse_frames


ADDR_DEFAULT = (os.environ.get("MELODYCTL_ADDR")
                or os.environ.get("ENCO_ADDR", "6C:0D:E1:5F:DB:4D"))
RFCOMM_CH = 12


class Buds:
    def __init__(self, addr: str = ADDR_DEFAULT, timeout: float = 10.0) -> None:
        self.addr = addr
        self.timeout = timeout
        self.sock: socket.socket | None = None
        self.seq = 0x20

    def __enter__(self) -> "Buds":
        self.connect()
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    def connect(self) -> None:
        if not hasattr(socket, "AF_BLUETOOTH"):
            raise MelodyctlError(
                "this Python has no Bluetooth socket support (socket.AF_BLUETOOTH)",
                code="no_bluetooth_support",
                hint="Install melodyctl with a system Python, e.g. 'uv tool install "
                     "--python /usr/bin/python3 git+https://github.com/chiragverma11/melodyctl'.",
            )
        s = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
        s.settimeout(self.timeout)
        s.connect((self.addr, RFCOMM_CH))
        self.sock = s
        self._hello()

    def close(self) -> None:
        if self.sock is not None:
            try:
                self.sock.close()
            finally:
                self.sock = None

    def _drain(self, wait: float) -> bytes:
        assert self.sock is not None
        end = time.time() + wait
        buf = bytearray()
        self.sock.settimeout(0.3)
        while time.time() < end:
            try:
                chunk = self.sock.recv(512)
                if not chunk:
                    break
                buf += chunk
                end = time.time() + 0.5
            except socket.timeout:
                continue
            except OSError:
                break
        return bytes(buf)

    def _hello(self) -> None:
        assert self.sock is not None
        self.sock.sendall(frame(CMD_HELLO, b"", 0x23))
        self._drain(2.0)

    def _next_seq(self) -> int:
        self.seq = (self.seq + 1) & 0xFF
        return self.seq

    def send(self, cmd: int, payload: bytes = b"", wait: float = 2.5) -> list[dict]:
        """Send one command, return the parsed response frames that match it."""
        assert self.sock is not None, "not connected"
        seq = self._next_seq()
        self.sock.sendall(frame(cmd, payload, seq))
        frames = parse_frames(self._drain(wait))
        want = cmd | RESP_FLAG
        return [f for f in frames if f["cmd"] == want]

    def raw(self, pkt: bytes, wait: float = 2.5) -> bytes:
        assert self.sock is not None, "not connected"
        self.sock.sendall(pkt)
        return self._drain(wait)

    # ---- high level --------------------------------------------------------
    def battery(self) -> dict:
        """Return {left,right,case} levels plus charging flags."""
        for f in self.send(CMD_BATT_GET):
            p = f["payload"]
            if len(p) < 2:
                continue
            # payload = [status/0x00][count][ (dev, charging<<7|level) * count ]
            count = p[1]
            out: dict[str, dict] = {}
            for k in range(count):
                idx = 2 + k * 2
                if idx + 1 >= len(p):
                    break
                dev = p[idx]
                val = p[idx + 1]
                out[COMPONENT.get(dev, f"id{dev}")] = {
                    "level": val & 0x7F,
                    "charging": bool(val & 0x80),
                }
            if out:
                return out
        raise ValueError("no battery response")

    def versions(self) -> list[dict]:
        """Decode the component version records (cmd 0x0105 response)."""
        for f in self.send(CMD_VERSION_GET):
            return decode_version_records(f["payload"])
        return []

    def set_eq(self, index: int) -> list[dict]:
        return self.send(CMD_EQ_SET, bytes([index & 0xFF]))

    def set_game_sound(self, gtype: int, enable: bool) -> list[dict]:
        return self.send(CMD_GAMESOUND_SET, bytes([gtype & 0xFF, 1 if enable else 0]))

    def caps(self) -> set[int]:
        """Return the set of command ids the device advertises."""
        for f in self.send(CMD_CAPS):
            return decode_caps(f["payload"])
        return set()

    def gestures(self) -> list[dict]:
        """Return the touch-gesture (key function) table."""
        for f in self.send(CMD_GESTURES_GET):
            return decode_gestures(f["payload"])
        return []

    def set_gesture(self, ear: int, button: int, action: int, function: int) -> list[dict]:
        """Assign ``function`` to (ear, button, action). Ack payload 0x00 = ok.

        ear 4 ("both") is expanded into two per-ear writes, since the device
        rejects combined-ear writes for some actions.
        """
        ears = [1, 2] if ear == 4 else [ear]
        out: list[dict] = []
        for e in ears:
            payload = bytes([1, e & 0xFF, button & 0xFF, action & 0xFF, function & 0xFF])
            out += self.send(CMD_GESTURES_SET, payload)
        return out

    def set_game_mode(self, enable: bool) -> list[dict]:
        """Toggle game (low-latency) mode: feature switch 0x0403, feature 6."""
        return self.send(CMD_SWITCH_FEATURE, bytes([FEATURE_GAME_MODE, 1 if enable else 0]))

    # ---- notifications -----------------------------------------------------
    def notify_caps(self) -> list[int]:
        """Subscribe (0x0200) and return the event ids the device can push."""
        for f in self.send(CMD_NOTIFY_SUB, wait=2.0):
            p = f["payload"]
            if len(p) >= 2:
                return list(p[2:2 + p[1]])
        return []

    def register_notify(self, events: list[int]) -> dict[int, int | None]:
        """Register event ids (0x0201). Returns {eventId: ackStatus}."""
        out: dict[int, int | None] = {}
        for e in events:
            r = self.send(CMD_NOTIFY_REG, bytes([e & 0xFF]), wait=1.5)
            out[e] = r[0]["payload"][0] if r and r[0]["payload"] else None
        return out


