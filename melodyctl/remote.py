"""Client side of the daemon link.

`melodyctl` commands try this first and fall back to their own RFCOMM session
whenever the socket is absent or unusable, so behaviour with no daemon running
is exactly the behaviour before the daemon existed. A *reply* is not a socket
failure: when the daemon answers with an error (for example while it is waiting
for cased earbuds) that error is reported, because the daemon is the owner of
the link and a direct connection would only fight it.
"""
from __future__ import annotations

import json
import socket

from .daemon import socket_path
from .errors import MelodyctlError
from .transport import ADDR_DEFAULT, Buds


class NoDaemon(Exception):
    """The socket is missing or unusable - use a direct RFCOMM session."""


def _connect(timeout: float | None) -> socket.socket:
    path = socket_path()
    if not path.exists():
        raise NoDaemon(f"no daemon socket at {path}")
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect(str(path))
    except OSError as exc:
        sock.close()
        raise NoDaemon(f"daemon socket {path} is not answering ({exc})") from None
    return sock


def _readline(sock: socket.socket) -> bytes:
    buf = bytearray()
    while b"\n" not in buf:
        chunk = sock.recv(4096)
        if not chunk:
            break
        buf += chunk
    line, _, _ = bytes(buf).partition(b"\n")
    return line


def request(payload: dict, timeout: float | None = 30.0) -> dict:
    """One request/response over the daemon socket. Raises NoDaemon if absent."""
    sock = _connect(timeout)
    try:
        sock.sendall(json.dumps(payload).encode("utf-8") + b"\n")
        line = _readline(sock)
    except OSError as exc:
        raise NoDaemon(f"lost the daemon socket: {exc}") from None
    finally:
        sock.close()
    if not line:
        raise NoDaemon("the daemon closed the connection without a reply")
    try:
        return json.loads(line.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise NoDaemon(f"unreadable daemon reply: {exc}") from None


def ping(timeout: float = 3.0) -> dict | None:
    """The daemon's hello reply, or None when no daemon is running."""
    try:
        reply = request({"op": "ping"}, timeout=timeout)
    except NoDaemon:
        return None
    return reply if reply.get("ok") else None


def subscribe():
    """Yield the daemon's stream objects: the hello, then events/transitions."""
    sock = _connect(None)          # blocking reads: quiet stretches are normal
    try:
        sock.sendall(b'{"op": "subscribe"}\n')
        while True:
            line = _readline(sock)
            if not line:
                raise MelodyctlError(
                    "the daemon closed the event stream",
                    code="daemon_gone",
                    hint="Is the daemon still running? Otherwise drop "
                         "--no-daemon to use a direct session.")
            yield json.loads(line.decode("utf-8"))
    finally:
        sock.close()


class RemoteBuds(Buds):
    """A `Buds`-shaped proxy whose frames travel over the daemon's session.

    Only the frame-level methods differ: every high-level call in `Buds`
    (`battery`, `caps`, `gestures`, `set_gesture`, ...) is expressed in terms
    of `send` / `send_frames` / `raw`, so they work unchanged through the
    daemon and the device still sees exactly one OPOv1 conversation.
    """

    def __init__(self, addr: str = ADDR_DEFAULT) -> None:
        super().__init__(addr)
        self.info: dict = {}

    def connect(self) -> None:
        info = ping()
        if info is None:
            raise NoDaemon("no daemon is running")
        self.info = info
        self.addr = info.get("addr") or self.addr
        self.channel = info.get("channel")
        self.lost = None

    def close(self) -> None:
        """Nothing to close: the daemon owns the link."""

    def reconnect(self, events=None, bulk: bool = False):
        self.connect()
        return None

    def send_frames(self, cmd: int, payload: bytes = b"", wait: float = 2.5) -> list[dict]:
        reply = self._call({"op": "send", "cmd": int(cmd),
                            "payload": payload.hex(), "wait": float(wait)},
                           timeout=float(wait) + 20.0)
        return [{"cmd": int(f["cmd"]), "payload": bytes.fromhex(f["payload"]),
                 "seq": 0} for f in reply.get("frames") or []]

    def raw(self, pkt: bytes, wait: float = 2.5) -> bytes:
        reply = self._call({"op": "raw", "packet": pkt.hex(), "wait": float(wait)},
                           timeout=float(wait) + 20.0)
        return bytes.fromhex(reply.get("reply") or "")

    def _call(self, payload: dict, timeout: float = 30.0) -> dict:
        try:
            reply = request(payload, timeout=timeout)
        except NoDaemon as exc:
            raise MelodyctlError(
                str(exc), code="daemon_gone",
                hint="Start the daemon again, or run the command with "
                     "--no-daemon to open a direct session.") from None
        if not reply.get("ok"):
            err = reply.get("error") or {}
            raise MelodyctlError(err.get("message") or "the daemon reported an error",
                                 code=err.get("code") or "daemon_error",
                                 hint=err.get("hint") or "")
        return reply
