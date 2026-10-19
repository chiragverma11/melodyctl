"""Transport layer: RFCOMM session (address, channel, connect, hello, send/receive)."""
from __future__ import annotations

import os
import socket
import time

from .errors import MelodyctlError
from .protocol import CMD_ANC_QUERY, CMD_ANC_SET, CMD_BATT_GET, CMD_CAPS, CMD_EQ_SET, CMD_GAMESOUND_SET, CMD_GESTURES_GET, CMD_GESTURES_SET, CMD_HELLO, CMD_NOTIFY_PUSH, CMD_NOTIFY_REG, CMD_NOTIFY_REG_MULTI, CMD_NOTIFY_SUB, CMD_SWITCH_FEATURE, CMD_VERSION_GET, COMPONENT, FEATURE_GAME_MODE, RESP_FLAG, RESP_NOTIFY_REGISTERED, RESP_NOTIFY_REG_MULTI, decode_caps, decode_gestures, decode_notify_event, decode_version_records, frame, notify_register_payload, parse_frames


ADDR_DEFAULT = (os.environ.get("MELODYCTL_ADDR")
                or os.environ.get("ENCO_ADDR", "6C:0D:E1:5F:DB:4D"))
RFCOMM_CH = 12                    # ETI81 (hw-verified); other models differ - OQ-3
CHANNEL_CANDIDATES = [RFCOMM_CH, 15]   # then a full 1..30 sweep
PROBE_TIMEOUT = 2.0               # per-channel cap while discovering
# errnos that mean "this session is gone", not "no data right now". The buds
# close the RFCOMM link when they idle or go back in the case with the lid
# shut [hw:ETI81 2026-10-19], and a closed socket keeps raising these. Anything
# else (EINTR, EAGAIN) is transient and must not be reported as a disconnect.
DEAD_ERRNOS = (5, 9, 19, 32, 104, 107, 110, 112, 113)


def _event_body(f: dict) -> bytes | None:
    """Return the notify event body carried by ``f``, or None if it carries none.

    Live pushes arrive on 0x0204; an asynchronous 0x8202 carries the same event
    body one byte later (a leading status byte) [apk:j#c].
    """
    if f["cmd"] == CMD_NOTIFY_PUSH:
        return f["payload"]
    if f["cmd"] == RESP_NOTIFY_REGISTERED and len(f["payload"]) >= 2:
        return f["payload"][1:]
    return None


def decode_push_frame(f: dict, oneplus_branch: bool = False,
                      product_id: str | None = None) -> dict | None:
    """Decode one 0x0204/0x8202 frame into an event dict, or None."""
    body = _event_body(f)
    if body is None:
        return None
    decoded = decode_notify_event(body, oneplus_branch, product_id)
    if not decoded:
        return None
    # keep the wire bytes and the frame that carried them: a capture cannot be
    # re-verified from decoded values alone, and 0x0204 pushes look identical
    # to 0x8202 snapshots once the event body is decoded
    decoded["via"] = f"0x{f['cmd']:04X}"
    decoded["hex"] = body.hex(" ").upper()
    return decoded


class Buds:
    def __init__(self, addr: str = ADDR_DEFAULT, timeout: float = 10.0,
                 channel: int | None = None) -> None:
        self.addr = addr
        self.timeout = timeout
        self.sock: socket.socket | None = None
        self.seq = 0x20
        self._pending_events: list[dict] = []
        self.lost: str | None = None   # set when the device closes the link
        env = os.environ.get("MELODYCTL_CHANNEL")
        self.channel = channel if channel is not None else (int(env) if env else None)
        self.channel_discovered = False

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
        self.sock = self._open_socket()
        self.lost = None
        self._hello()

    def reconnect(self, events: list[int] | None = None,
                  bulk: bool = False) -> dict | None:
        """Drop the dead socket, connect again, and optionally re-register.

        Needed because the device closes the link when it idles or is cased:
        the old socket stays mute forever, so a watcher must build a new one
        [hw:ETI81 2026-10-19]. Returns the ``register_notify`` result when
        ``events`` is given, else ``None``.
        """
        self.close()
        self.connect()
        if events is None:
            return None
        return self.register_notify(events, bulk=bulk)

    # ---- channel discovery -------------------------------------------------
    def _open_socket(self) -> socket.socket:
        """Connect, discovering the RFCOMM channel when it is not known.

        The Python stdlib has no SDP, so discovery is a probe: the ETI81
        value, the prior-art value, then a 1..30 sweep. Address-level errors
        (busy / host down / no adapter) abort instead of sweeping.
        """
        if self.channel is not None:
            return self._connect_channel(self.channel)
        last: OSError | None = None
        order = CHANNEL_CANDIDATES + [c for c in range(1, 31)
                                      if c not in CHANNEL_CANDIDATES]
        for ch in order:
            try:
                sock = self._connect_channel(ch, timeout=PROBE_TIMEOUT)
            except OSError as exc:
                if exc.errno in (16, 19, 112, 113):  # busy / no adapter / host down
                    raise
                last = exc
                continue
            self.channel = ch
            self.channel_discovered = True
            return sock
        raise MelodyctlError(
            f"no RFCOMM channel accepted a connection on {self.addr}",
            code="no_channel",
            hint=f"probed channels 1-30 (last error: {last}); is the device awake, "
                 f"paired and not held by another app?",
        )

    def _connect_channel(self, channel: int, timeout: float | None = None) -> socket.socket:
        s = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
        s.settimeout(timeout if timeout is not None else self.timeout)
        try:
            s.connect((self.addr, channel))
        except OSError:
            s.close()
            raise
        return s

    def close(self) -> None:
        if self.sock is not None:
            try:
                self.sock.close()
            finally:
                self.sock = None

    def _drain(self, wait: float) -> bytes:
        """Read for up to ``wait`` seconds, recording a dead link in ``lost``.

        A socket the device closed never becomes readable again, so callers
        that loop (``iter_events``) must check ``lost`` instead of waiting
        forever for data that cannot arrive [hw:ETI81 2026-10-19].
        """
        assert self.sock is not None
        end = time.time() + wait
        buf = bytearray()
        self.sock.settimeout(0.3)
        while time.time() < end:
            try:
                chunk = self.sock.recv(512)
            except socket.timeout:
                continue
            except OSError as exc:
                if exc.errno in DEAD_ERRNOS:
                    self.lost = exc.strerror or exc.__class__.__name__
                break
            if not chunk:
                self.lost = "peer closed the connection"
                break
            buf += chunk
            end = time.time() + 0.5
        return bytes(buf)

    def _hello(self) -> None:
        assert self.sock is not None
        self.sock.sendall(frame(CMD_HELLO, b"", 0x23))
        self._drain(2.0)

    def _next_seq(self) -> int:
        self.seq = (self.seq + 1) & 0xFF
        return self.seq

    def send_frames(self, cmd: int, payload: bytes = b"", wait: float = 2.5) -> list[dict]:
        """Send one command and return every parsed reply frame."""
        assert self.sock is not None, "not connected"
        seq = self._next_seq()
        self.sock.sendall(frame(cmd, payload, seq))
        return parse_frames(self._drain(wait))

    def send(self, cmd: int, payload: bytes = b"", wait: float = 2.5) -> list[dict]:
        """Send one command, return the parsed response frames that match it."""
        want = cmd | RESP_FLAG
        return [f for f in self.send_frames(cmd, payload, wait) if f["cmd"] == want]

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

    def gestures(self, oneplus_branch: bool = False) -> list[dict]:
        """Return the touch-gesture (key function) table."""
        for f in self.send(CMD_GESTURES_GET):
            return decode_gestures(f["payload"], oneplus_branch)
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

    # ---- noise cancelling --------------------------------------------------
    def anc_query(self) -> list[dict]:
        """Query the active noise-cancelling state (0x010c -> 0x810c)."""
        return self.send(CMD_ANC_QUERY, b"\x01\x01")

    def anc_set(self, bitmap: bytes) -> list[dict]:
        """Set the ANC bitmap (0x0404). The ack is not proof - re-query after."""
        return self.send(CMD_ANC_SET, b"\x01\x01" + bitmap)

    # ---- notifications -----------------------------------------------------
    def notify_caps(self) -> list[int]:
        """Subscribe (0x0200) and return the event ids the device can push."""
        for f in self.send(CMD_NOTIFY_SUB, wait=2.0):
            p = f["payload"]
            if len(p) >= 2:
                return list(p[2:2 + p[1]])
        return []

    def register_notify(self, events: list[int],
                        bulk: bool = False) -> dict:
        """Register event ids for push delivery.

        ``bulk=True`` sends the app's single ``0x0205`` (it uses that whenever
        the device advertises the command); if no ``0x8205`` ack arrives within
        the window we fall back to one ``0x0201`` per event [apk:j#c]. Returns
        ``{"style": "bulk"|"per-event", "acks": {eventId: ackStatus|None}}``.

        A device-initiated ``0x8202`` seen along the way is buffered so
        ``iter_events`` can yield its value first.
        """
        events = [e & 0xFF for e in events]
        self._pending_events = []
        bulk_attempted = False
        if bulk and len(events) > 1:
            bulk_attempted = True
            frames = self.send_frames(CMD_NOTIFY_REG_MULTI,
                                      notify_register_payload(events), wait=2.0)
            self._pending_events += [f for f in frames
                                     if f["cmd"] == RESP_NOTIFY_REGISTERED]
            ack = next((f for f in frames if f["cmd"] == RESP_NOTIFY_REG_MULTI), None)
            # Only a clean ack counts: a refusal (non-zero status) must fall
            # back rather than leave us subscribed to nothing.
            if ack is not None and (not ack["payload"] or ack["payload"][0] == 0):
                return {"style": "bulk", "acks": {e: None for e in events},
                        "bulk_attempted": True}
        acks: dict[int, int | None] = {}
        for e in events:
            frames = self.send_frames(CMD_NOTIFY_REG, bytes([e]), wait=1.5)
            ack = next((f for f in frames
                        if f["cmd"] == CMD_NOTIFY_REG | RESP_FLAG), None)
            acks[e] = ack["payload"][0] if ack and ack["payload"] else None
            self._pending_events += [f for f in frames
                                     if f["cmd"] == RESP_NOTIFY_REGISTERED]
        return {"style": "per-event", "acks": acks,
                "bulk_attempted": bulk_attempted}

    def iter_events(self, drain: float = 1.0, oneplus_branch: bool = False,
                    product_id: str | None = None):
        """Yield decoded pushes until interrupted or the link dies.

        A convenience wrapper over ``read_events`` for callers that do nothing
        else while watching. Anything that must interleave its own work (the
        daemon answers client requests) should call ``read_events`` in a loop
        instead: a generator only returns from ``next()`` when it actually has
        an event, so on an edge-triggered, mostly-silent device the generator
        starves whatever else the caller wanted to do.
        """
        while True:
            for ev in self.read_events(drain, oneplus_branch, product_id):
                yield ev

    def read_events(self, wait: float = 1.0, oneplus_branch: bool = False,
                    product_id: str | None = None) -> list[dict]:
        """Read for up to ``wait`` seconds and return the decoded pushes.

        Always returns within roughly ``wait`` seconds (a burst of frames keeps
        the read alive until the device goes quiet for 0.5 s), so a caller can
        interleave other work between calls. Raises ``MelodyctlError(code=
        "disconnected")`` when the device closed the link.

        Live pushes arrive on 0x0204; an asynchronous 0x8202 carries the same
        event body one byte later (a leading status byte) [apk:j#c].
        """
        out: list[dict] = []
        pending, self._pending_events = self._pending_events, []
        for f in pending:
            decoded = decode_push_frame(f, oneplus_branch, product_id)
            if decoded:
                out.append(decoded)
        for f in parse_frames(self._drain(wait)):
            decoded = decode_push_frame(f, oneplus_branch, product_id)
            if decoded:
                out.append(decoded)
        # A push that arrived just before the peer closed is still real data:
        # hand it over, and let the next call report the disconnect.
        if self.lost and not out:
            raise MelodyctlError(
                f"the earbuds closed the connection ({self.lost})",
                code="disconnected",
                hint="They do this when they idle, or go back in the case "
                     "with the lid closed. Start 'melodyctl watch' again, or "
                     "pass '--reconnect' to sit through it and keep watching.",
            )
        return out


