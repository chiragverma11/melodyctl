"""melodyctl daemon: the single owner of the RFCOMM link.

The device allows one RFCOMM connection at a time, and the push channel is
worth holding open (pushes are edge-triggered, so the battery/bud-state a
`watch` session collects is the freshest data the device will ever hand out
[hw:ETI81 2026-10-19]). This mirrors what the app itself does: a long-lived
notification session next to the polling one [apk:HeadsetCoreService].

So the daemon holds the link and everything else reads from it:

    $XDG_RUNTIME_DIR/melodyctl/state.json   last known state, for file readers
    $XDG_RUNTIME_DIR/melodyctl/daemon.sock  line-delimited JSON, for commands

Threading: the session thread is the only thread that ever touches the device.
Client `send` requests are handed to it through a queue and executed between
drains, so OPOv1 frames never interleave. A push that lands inside a request's
reply window is routed to the same handler as one read from the stream - it
must not be swallowed by that window.
"""
from __future__ import annotations

import fcntl
import json
import os
import queue
import signal
import socket
import threading
import time
from pathlib import Path

from . import __version__
from .devices import oneplus_branch, profile_for
from .errors import MelodyctlError, classify_error
from .protocol import (CMD_BATT_GET, CMD_INFO, CMD_NOTIFY_PUSH,
                       CMD_NOTIFY_REG_MULTI, CMD_SWITCH_FEATURE,
                       FEATURE_GAME_MODE, NOTIFY_BATTERY, NOTIFY_BUD_STATUS,
                       NOTIFY_GAME_MODE, RESP_FLAG, RESP_NOTIFY_REGISTERED,
                       decode_battery_event, decode_product_id)
from .transport import ADDR_DEFAULT, Buds, decode_push_frame

HEARTBEAT = 60.0     # rewrite state.json this often so `ts` stays meaningful
POLL = 120.0         # quiet-link battery read; also proves the link is alive
DRAIN = 0.25         # seconds one read waits before the queue is serviced
JOB_TIMEOUT = 30.0   # how long a client waits for the session thread
QUEUE_MAX = 256      # per-subscriber backlog before pushes are dropped

# A link loss is routine (the buds idle, or go back in the case); the hint the
# transport carries is written for a direct `watch` session, so the daemon
# publishes its own wording instead of advising a command the user is not running.
DAEMON_HINTS = {
    "disconnected": "The earbuds closed the link (idle, or back in the case). "
                    "The daemon reconnects automatically.",
}


def runtime_dir() -> Path:
    """Our runtime directory: under XDG_RUNTIME_DIR, else a per-uid /tmp path."""
    base = os.environ.get("XDG_RUNTIME_DIR")
    root = Path(base) if base else Path(f"/tmp/melodyctl-{os.getuid()}")
    return root / "melodyctl"


def socket_path() -> Path:
    return runtime_dir() / "daemon.sock"


def state_path() -> Path:
    return runtime_dir() / "state.json"


def lock_path() -> Path:
    return runtime_dir() / "daemon.lock"


def write_json(path: Path, payload: dict) -> None:
    """Write ``payload`` as one JSON line, atomically (tmp + rename)."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _error(exc: BaseException) -> dict:
    """classify_error + message, in the CLI's error shape."""
    code, hint = classify_error(exc)
    message = (getattr(exc, "strerror", None) or str(exc)
               or exc.__class__.__name__)
    err = {"code": code, "message": message}
    hint = DAEMON_HINTS.get(code, hint)
    if hint:
        err["hint"] = hint
    return err


class _Job:
    """One client request, run by the session thread."""

    __slots__ = ("req", "done", "reply")

    def __init__(self, req: dict) -> None:
        self.req = req
        self.done = threading.Event()
        self.reply: dict | None = None


class Daemon:
    """Holds the link, publishes state.json, serves daemon.sock."""

    def __init__(self, addr: str = ADDR_DEFAULT, retry_max: float = 60.0,
                 drain: float = DRAIN, heartbeat: float = HEARTBEAT,
                 poll: float = POLL, quiet: bool = False) -> None:
        self.addr = addr
        self.retry_max = max(1.0, retry_max)
        self.drain = drain
        self.heartbeat = heartbeat
        self.poll = max(0.0, poll)
        self.quiet = quiet
        self.debug = bool(os.environ.get("MELODYCTL_DEBUG"))
        self.stop = threading.Event()
        self._lock_file = None
        self._jobs: queue.Queue[_Job] = queue.Queue()
        self._subscribers: list[queue.Queue] = []
        self._sub_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._oneplus = False
        self._product: str | None = None
        self._last_data = time.time()   # when the device last told us anything
        self.state: dict = {
            "version": __version__,
            "addr": addr,
            "session": "waiting",
            "product": None,
            "device": None,
            "channel": None,
            "registered": [],
            "battery": None,
            "status": None,
            "game": None,
            "updated": None,
            "ts": time.time(),
            "error": None,
        }

    # ---- lifecycle ---------------------------------------------------------
    def log(self, message: str) -> None:
        if not self.quiet:
            print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)

    def dbg(self, message: str) -> None:
        """Timing detail for diagnosing a stuck client (MELODYCTL_DEBUG=1)."""
        if self.debug:
            print(f"[{time.strftime('%H:%M:%S')}] * {message}", flush=True)

    def acquire_lock(self) -> None:
        path = lock_path()
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        handle = open(path, "w", encoding="utf-8")
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            raise MelodyctlError(
                "another melodyctl daemon is already running",
                code="daemon_running",
                hint=f"lock file: {path} - stop it first "
                     f"('systemctl --user stop melodyctl-daemon'), or run the "
                     f"command with --no-daemon.",
            ) from None
        handle.write(f"{os.getpid()}\n")
        handle.flush()
        self._lock_file = handle

    def run(self) -> int:
        self.acquire_lock()
        signal.signal(signal.SIGTERM, self._on_signal)
        signal.signal(signal.SIGINT, self._on_signal)
        self.log(f"melodyctl daemon {__version__} - addr {self.addr}")
        self.log(f"state {state_path()}")
        self.log(f"socket {socket_path()}")
        self._write_state()
        session = threading.Thread(target=self._session_loop, name="session",
                                   daemon=True)
        session.start()
        try:
            self._serve()
        finally:
            self.stop.set()
            session.join(timeout=5.0)
            self._cleanup()
            self.log("stopped")
        return 0

    def _on_signal(self, *_args) -> None:
        self.stop.set()

    def _cleanup(self) -> None:
        """Wake subscribers, drop the socket, and leave no stale state behind."""
        with self._sub_lock:
            for q in self._subscribers:
                try:
                    q.put_nowait(None)
                except queue.Full:
                    pass
            self._subscribers.clear()
        self.release_lock()
        try:
            socket_path().unlink(missing_ok=True)
        except OSError:
            pass
        try:
            state_path().unlink(missing_ok=True)
        except OSError:
            pass

    def release_lock(self) -> None:
        """Drop the lock file handle (the flock is released by the close)."""
        if self._lock_file is not None:
            try:
                self._lock_file.close()
            except OSError:
                pass
            self._lock_file = None

    # ---- state -------------------------------------------------------------
    def _snapshot(self) -> dict:
        with self._state_lock:
            return dict(self.state)

    def _set_state(self, session: str, notify: bool = True, **fields) -> None:
        with self._state_lock:
            self.state.update(fields)
            self.state["session"] = session
        self._write_state()
        if notify:
            snap = self._snapshot()
            self._broadcast({"session": session, "product": snap["product"],
                             "device": snap["device"], "channel": snap["channel"],
                             "registered": snap["registered"],
                             "error": snap["error"]})

    def _write_state(self, heartbeat: bool = False) -> None:
        with self._state_lock:
            self.state["ts"] = time.time()
            payload = dict(self.state)
        try:
            write_json(state_path(), payload)
        except OSError as exc:
            self.log(f"! cannot write state: {exc}")

    def _broadcast(self, item: dict) -> None:
        with self._sub_lock:
            subs = list(self._subscribers)
        for q in subs:
            try:
                q.put_nowait(item)
            except queue.Full:
                pass

    def _handle_event(self, ev: dict) -> None:
        """Merge one decoded push into the snapshot, then fan it out."""
        ev.setdefault("ts", time.time())
        eid = ev.get("event_id")
        when = None
        with self._state_lock:
            if eid == NOTIFY_BATTERY:
                self.state["battery"] = ev.get("battery") or None
            elif eid == NOTIFY_BUD_STATUS:
                self.state["status"] = ev.get("status") or None
            elif eid == NOTIFY_GAME_MODE and ev.get("game"):
                self.state["game"] = ev["game"]
            if eid in (NOTIFY_BATTERY, NOTIFY_BUD_STATUS, NOTIFY_GAME_MODE):
                when = ev.get("ts") or time.time()
                self.state["updated"] = when
                self.state["error"] = None
        if when is not None:
            self._last_data = when
        self._write_state()
        self._broadcast({"event": ev})

    def _apply_battery(self, battery: dict | None, when: float | None = None) -> None:
        """Record a battery reading obtained by a poll, not by a push.

        The reading *is* current device data, so it updates ``battery`` and
        ``updated``; it is not broadcast, because an attached ``watch`` is a
        push stream and a poll is not a push.
        """
        now = when or time.time()
        with self._state_lock:
            self.state["battery"] = battery or None
            self.state["updated"] = now
            self.state["error"] = None
        self._last_data = now
        self._write_state()

    @staticmethod
    def _decode_battery_reply(payload: bytes) -> dict:
        """Decode a `0x0106` reply payload (`[status][count][...]`)."""
        if len(payload) < 2:
            return {}
        return decode_battery_event(payload[1:])

    def _poll_battery(self, conn: Buds) -> dict:
        """Read the battery now, folding any push caught in the reply window."""
        battery: dict = {}
        pushed = None
        for f in conn.send_frames(CMD_BATT_GET):
            if f["cmd"] in (CMD_NOTIFY_PUSH, RESP_NOTIFY_REGISTERED):
                ev = self._handle_push(f["cmd"], f["payload"])
                if ev and ev.get("event_id") == NOTIFY_BATTERY:
                    pushed = ev.get("battery")
            elif f["cmd"] == CMD_BATT_GET | RESP_FLAG:
                battery = self._decode_battery_reply(f["payload"]) or battery
        if conn.lost:
            raise MelodyctlError(conn.lost, code="disconnected")
        # A push that landed while we waited is newer than the reply.
        return pushed or battery

    def _clear_stale_game(self, payload: bytes) -> None:
        """Forget a pushed game value that a served command just replaced.

        The device only reports game mode as push event 5, and only after a
        *gesture* that changes it (claim #48) - a `0x0403` write is not echoed,
        and there is no read-back, so the snapshot cannot be refreshed. Keeping
        the pre-command value would make state.json (and the widget) claim a
        state the command just changed; null it when it disagrees, and let the
        next event 5 restore a device-reported value.
        """
        if len(payload) < 2 or payload[0] != FEATURE_GAME_MODE:
            return
        want_on = payload[1] != 0
        with self._state_lock:
            game = self.state.get("game")
            if not game or bool(game.get("on")) == want_on:
                return
            self.state["game"] = None
        self.dbg(f"game -> {'on' if want_on else 'off'}: "
                 f"cleared the stale pushed value")
        self._write_state()

    # ---- device session ----------------------------------------------------
    def _session_loop(self) -> None:
        delay = 2.0
        while not self.stop.is_set():
            try:
                self._hold()
                delay = 2.0
            except Exception as exc:  # noqa: BLE001 - any failure = "no link"
                if self.stop.is_set():
                    break
                err = _error(exc)
                self.log(f"not connected: {err['message']} "
                         f"(retrying in {delay:.0f}s)")
                self._set_state("waiting", error=err)
                # Answer queued clients while we back off, and treat a client
                # that is actively asking as a reason to try again right away
                # (a polling widget would otherwise wait out the whole back-off
                # before the buds are noticed). The heartbeat runs here too, so
                # `ts` always means "the daemon is alive and this is its latest
                # word" - a reader judges freshness on that alone.
                deadline = time.time() + delay
                last_write = time.time()
                demand = False
                while not self.stop.is_set() and time.time() < deadline:
                    if self._fail_jobs(err, wait=0.5):
                        demand = True
                        break
                    if time.time() - last_write >= self.heartbeat:
                        self._write_state()
                        last_write = time.time()
                delay = 2.0 if demand else min(delay * 2, self.retry_max)

    def _hold(self) -> None:
        """One session: identify, subscribe, then hold and fan out pushes."""
        t0 = time.time()
        conn = Buds(self.addr)
        conn.connect()
        self.dbg(f"link up in {time.time() - t0:.1f}s")
        try:
            frames = conn.send(CMD_INFO)
            pid = decode_product_id(frames[0]["payload"]) if frames else None
            profile = profile_for(pid)
            self._product = pid
            self._oneplus = oneplus_branch(profile)
            advertised = conn.notify_caps()
            bulk = CMD_NOTIFY_REG_MULTI in conn.caps()
            reg = (conn.register_notify(advertised, bulk=bulk) if advertised
                   else {"style": "none", "acks": {}})
            battery = None
            try:
                battery = conn.battery()
            except ValueError as exc:
                # no reply: the link is up, so keep it and seed on the next
                # drain/poll rather than dropping a usable session
                self.log(f"battery poll failed: {exc}")
            name = profile.get("name") if profile else None
            self.dbg(f"handshake done in {time.time() - t0:.1f}s")
            self.log(f"connected: {pid or '?'} ({name or 'unknown'}) on channel "
                     f"{conn.channel}; registered {advertised} via {reg['style']}")
            # `updated` is "when the device last told us something": the seed
            # read is such a moment, so carrying the previous session's time
            # over would let a reader date fresh levels to an old push.
            self._set_state("connected", product=pid, device=name,
                            channel=conn.channel, registered=advertised,
                            battery=battery, status=None, game=None, error=None,
                            updated=(time.time() if battery else None))
            self._last_data = time.time()
            last_write = time.time()
            poll_fails = 0
            # read_events, not iter_events: the generator only returns from
            # next() once it has an event, so on this edge-triggered device the
            # loop would stop servicing client requests for minutes at a time.
            while not self.stop.is_set():
                self._serve_jobs(conn)
                if time.time() - last_write >= self.heartbeat:
                    self._write_state()
                    last_write = time.time()
                for ev in conn.read_events(self.drain, self._oneplus, pid):
                    self._handle_event(ev)
                if self.poll > 0 and time.time() - self._last_data >= self.poll:
                    # Quiet link: refresh the one value we can query. This also
                    # proves the peer is still there - a slept bud can leave the
                    # socket open and simply stop answering, which no read can
                    # detect.
                    try:
                        fresh = self._poll_battery(conn)
                    except MelodyctlError:
                        raise               # the link itself is gone
                    except Exception as exc:  # noqa: BLE001 - not a reply
                        raise MelodyctlError(
                            "the earbuds stopped answering (battery poll)",
                            code="disconnected") from exc
                    if fresh:
                        poll_fails = 0
                        self._apply_battery(fresh)
                    else:
                        poll_fails += 1
                        if poll_fails >= 2:
                            raise MelodyctlError(
                                "the earbuds stopped answering (battery poll)",
                                code="disconnected")
                        self._last_data = time.time()   # one more interval
        finally:
            self._product = None
            self._oneplus = False
            conn.close()

    def _serve_jobs(self, conn: Buds) -> None:
        while True:
            try:
                job = self._jobs.get_nowait()
            except queue.Empty:
                return
            op = job.req.get("op")
            self.dbg(f"serving {op}")
            job.reply = self._run(conn, job.req)
            job.done.set()
            self.dbg(f"served {op}: {(job.reply or {}).get('ok')}")

    def _fail_jobs(self, err: dict, wait: float) -> bool:
        """Answer requests while there is no link - never hang a client.

        Returns True when at least one request was answered, which the caller
        reads as demand for an immediate reconnect attempt.
        """
        answered = False
        deadline = time.time() + wait
        while True:
            left = deadline - time.time()
            if left <= 0:
                return answered
            try:
                job = self._jobs.get(timeout=min(left, 0.25))
            except queue.Empty:
                continue
            job.reply = {"ok": False, "error": dict(err)}
            job.done.set()
            answered = True

    def _run(self, conn: Buds, req: dict) -> dict:
        op = req.get("op")
        try:
            if op == "send":
                cmd = int(req["cmd"])
                payload = bytes.fromhex(req.get("payload") or "")
                wait = float(req.get("wait") or 2.5)
                out: list[dict] = []
                pushed_battery = False
                for f in conn.send_frames(cmd, payload, wait):
                    if f["cmd"] in (CMD_NOTIFY_PUSH, RESP_NOTIFY_REGISTERED):
                        # a push landing inside the reply window: same handler
                        # as one read from the stream, or it is lost
                        ev = self._handle_push(f["cmd"], f["payload"])
                        if ev and ev.get("event_id") == NOTIFY_BATTERY:
                            pushed_battery = True
                        continue
                    out.append({"cmd": f["cmd"], "payload": f["payload"].hex()})
                if cmd == CMD_BATT_GET and not pushed_battery:
                    # A client's battery read is device data too: keep the
                    # snapshot (and its `updated`) in step with what it got.
                    # A push that beat the reply is newer, so it wins.
                    for f in out:
                        if f["cmd"] == CMD_BATT_GET | RESP_FLAG:
                            fresh = self._decode_battery_reply(
                                bytes.fromhex(f["payload"]))
                            if fresh:
                                self._apply_battery(fresh)
                            break
                if cmd == CMD_SWITCH_FEATURE and any(
                        f["cmd"] == CMD_SWITCH_FEATURE | RESP_FLAG
                        and f["payload"] == "00" for f in out):
                    self._clear_stale_game(payload)
                return {"ok": True, "frames": out}
            if op == "raw":
                reply = conn.raw(bytes.fromhex(req.get("packet") or ""),
                                 float(req.get("wait") or 2.5))
                return {"ok": True, "reply": reply.hex()}
        except Exception as exc:  # noqa: BLE001 - reported to the client as JSON
            return {"ok": False, "error": _error(exc)}
        return {"ok": False, "error": {"code": "bad_request",
                                       "message": f"unknown op {op!r}"}}

    def _handle_push(self, cmd: int, payload: bytes) -> dict | None:
        """Decode a 0x0204 / 0x8202 frame caught in a reply window."""
        ev = decode_push_frame({"cmd": cmd, "payload": payload},
                               self._oneplus, self._product)
        if ev:
            self._handle_event(ev)
        return ev

    # ---- socket server -----------------------------------------------------
    def _serve(self) -> None:
        path = socket_path()
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if path.exists():
            path.unlink()          # we hold the lock, so this is a leftover
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            listener.bind(str(path))
            os.chmod(path, 0o600)
            listener.listen(16)
            listener.settimeout(0.5)
            while not self.stop.is_set():
                try:
                    conn, _ = listener.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break
                threading.Thread(target=self._client, args=(conn,),
                                 daemon=True).start()
        finally:
            listener.close()

    def _client(self, conn: socket.socket) -> None:
        try:
            stream = conn.makefile("rwb")
            line = stream.readline()
            if not line:
                return
            try:
                req = json.loads(line.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                self._reply(stream, {"ok": False, "error": {
                    "code": "bad_request",
                    "message": "expected one JSON object per line"}})
                return
            if not isinstance(req, dict):
                self._reply(stream, {"ok": False, "error": {
                    "code": "bad_request", "message": "expected a JSON object"}})
                return
            op = req.get("op")
            if op == "subscribe":
                self._subscribe(stream)
            elif op == "ping":
                self._reply(stream, self._ping())
            elif op == "state":
                self._reply(stream, {"ok": True, "state": self._snapshot()})
            else:
                self._reply(stream, self._job(req))
        except OSError:
            pass
        finally:
            try:
                conn.close()
            except OSError:
                pass

    @staticmethod
    def _reply(stream, payload: dict) -> None:
        stream.write((json.dumps(payload) + "\n").encode("utf-8"))
        stream.flush()

    def _ping(self) -> dict:
        snap = self._snapshot()
        return {"ok": True, "version": __version__, "pid": os.getpid(),
                "addr": snap["addr"], "channel": snap["channel"],
                "product": snap["product"], "device": snap["device"],
                "session": snap["session"], "registered": snap["registered"],
                "error": snap["error"], "ts": snap["ts"]}

    def _job(self, req: dict) -> dict:
        started = time.time()
        job = _Job(req)
        what = req.get("op")
        if "cmd" in req:
            what += f" cmd=0x{int(req['cmd']):04X}"
        self.dbg(f"queued {what}")
        self._jobs.put(job)
        if not job.done.wait(JOB_TIMEOUT):
            self.dbg(f"! {what} not served within {JOB_TIMEOUT:.0f}s")
            return {"ok": False, "error": {
                "code": "timeout",
                "message": "the device session did not answer in time"}}
        self.dbg(f"-> {what} after {time.time() - started:.2f}s")
        return job.reply or {"ok": False, "error": {
            "code": "error", "message": "no reply"}}

    def _subscribe(self, stream) -> None:
        """Stream pushes and session transitions to one client until it goes."""
        q: queue.Queue = queue.Queue(maxsize=QUEUE_MAX)
        with self._sub_lock:
            self._subscribers.append(q)
        try:
            snap = self._snapshot()
            self._reply(stream, {"ok": True, "link": "daemon",
                                 "addr": snap["addr"], "session": snap["session"],
                                 "product": snap["product"],
                                 "device": snap["device"],
                                 "channel": snap["channel"],
                                 "registered": snap["registered"],
                                 "error": snap["error"], "ts": snap["ts"]})
            while not self.stop.is_set():
                try:
                    item = q.get(timeout=0.5)
                except queue.Empty:
                    continue
                if item is None:
                    break
                self._reply(stream, item)
        except OSError:
            pass
        finally:
            with self._sub_lock:
                if q in self._subscribers:
                    self._subscribers.remove(q)
