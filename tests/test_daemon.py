"""Daemon + client-link tests.

Everything here runs without the earbuds: the daemon's session thread is
replaced by a fake `Buds`, and the socket side is exercised against a tiny
in-process stand-in. Runtime paths are redirected with XDG_RUNTIME_DIR so a
real daemon on the machine is never touched.
"""
import json
import os
import socket
import threading
import time
import unittest

from melodyctl import daemon, remote
from melodyctl.errors import MelodyctlError
from melodyctl.protocol import (CMD_BATT_GET, CMD_INFO, CMD_SWITCH_FEATURE,
                                RESP_FLAG)
from melodyctl.transport import Buds


class FakeBuds(Buds):
    """A Buds whose frames are canned - no Bluetooth involved."""

    def __init__(self, replies: dict | None = None) -> None:
        super().__init__("00:00:00:00:00:01")
        self.replies = replies or {}
        self.sent: list[tuple[int, bytes]] = []

    def connect(self) -> None:
        self.sock = object()          # only used as a liveness marker
        self.channel = 12

    def close(self) -> None:
        self.sock = None

    def send_frames(self, cmd, payload=b"", wait=2.5):
        self.sent.append((cmd, payload))
        return self.replies.get(cmd, [])

    def raw(self, pkt, wait=2.5):
        self.sent.append((-1, pkt))
        return b"\xaa\x03\x00\x00"


class FakeDaemon:
    """A one-thread stand-in for the daemon socket, with a canned handler."""

    def __init__(self, handler) -> None:
        self.handler = handler
        self.streams: list = []
        self.path = daemon.socket_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.bind(str(self.path))
        self.sock.listen(4)
        self.sock.settimeout(0.2)
        self.stop = False
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self) -> None:
        while not self.stop:
            try:
                conn, _ = self.sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(target=self._session, args=(conn,), daemon=True).start()

    def _session(self, conn) -> None:
        stream = None
        try:
            stream = conn.makefile("rwb")
            while True:
                line = stream.readline()
                if not line:
                    return
                self.handler(json.loads(line.decode()), stream)
        except OSError:
            pass
        finally:
            if stream is not None:
                try:
                    stream.close()
                except OSError:
                    pass
            try:
                conn.close()
            except OSError:
                pass

    def close(self) -> None:
        self.stop = True
        self.thread.join(timeout=2.0)
        self.sock.close()
        self.path.unlink(missing_ok=True)


class Base(unittest.TestCase):
    def setUp(self) -> None:
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self._env = os.environ.get("XDG_RUNTIME_DIR")
        os.environ["XDG_RUNTIME_DIR"] = self.tmp.name
        self.addCleanup(self._restore)

    def _restore(self) -> None:
        if self._env is None:
            os.environ.pop("XDG_RUNTIME_DIR", None)
        else:
            os.environ["XDG_RUNTIME_DIR"] = self._env
        self.tmp.cleanup()


class Paths(Base):
    def test_runtime_dir_follows_xdg(self):
        self.assertEqual(daemon.runtime_dir(), daemon.Path(self.tmp.name) / "melodyctl")
        self.assertTrue(str(daemon.socket_path()).endswith("melodyctl/daemon.sock"))

    def test_write_json_is_one_line_and_atomic(self):
        path = daemon.state_path()
        daemon.write_json(path, {"a": 1, "b": [2]})
        raw = path.read_text()
        self.assertEqual(raw.count("\n"), 1)
        self.assertEqual(json.loads(raw), {"a": 1, "b": [2]})
        self.assertEqual([p.name for p in path.parent.glob("*.tmp")], [])


class Lock(Base):
    def test_second_daemon_is_refused(self):
        first = daemon.Daemon()
        first.acquire_lock()
        self.addCleanup(first.release_lock)
        second = daemon.Daemon()
        with self.assertRaises(Exception) as ctx:
            second.acquire_lock()
        self.assertIn("already running", str(ctx.exception))


class Snapshot(Base):
    def _daemon(self):
        d = daemon.Daemon()
        d.acquire_lock()
        self.addCleanup(d.release_lock)
        return d

    def test_events_merge_into_state(self):
        d = self._daemon()
        d._handle_event({"event_id": 1, "battery": {"left": {"level": 50}}, "ts": 5})
        d._handle_event({"event_id": 2, "status": {"left": {"in_case": False}}, "ts": 6})
        d._handle_event({"event_id": 5, "game": {"on": True, "state": 1}, "ts": 7})
        state = json.loads(daemon.state_path().read_text())
        self.assertEqual(state["battery"]["left"]["level"], 50)
        self.assertEqual(state["status"]["left"]["in_case"], False)
        self.assertEqual(state["game"], {"on": True, "state": 1})
        self.assertEqual(state["updated"], 7)

    def test_gesture_events_do_not_touch_the_snapshot(self):
        # a tap is not state: it must not clobber battery/status and must not
        # claim a state update either
        d = self._daemon()
        d._handle_event({"event_id": 1, "battery": {"left": {"level": 50}}, "ts": 5})
        d._handle_event({"event_id": 241, "interaction": {"ear": "left"}, "ts": 9})
        state = json.loads(daemon.state_path().read_text())
        self.assertEqual(state["battery"]["left"]["level"], 50)
        self.assertEqual(state["updated"], 5)

    def test_dropped_components_disappear(self):
        # both buds out: the device stops listing the case, and so must we
        d = self._daemon()
        d._handle_event({"event_id": 1, "battery": {"left": {}, "right": {}, "case": {}}})
        d._handle_event({"event_id": 1, "battery": {"left": {}, "right": {}}})
        state = json.loads(daemon.state_path().read_text())
        self.assertNotIn("case", state["battery"])

    def test_session_transition_is_broadcast(self):
        d = self._daemon()
        received: list[dict] = []
        with d._sub_lock:
            q = d._subscribers[0] if d._subscribers else None
        self.assertIsNone(q)
        d._broadcast({"probe": 1})          # no subscribers: must not raise
        d._subscribers.append(_Collector(received))
        d._set_state("waiting", error={"code": "unreachable", "message": "no"})
        self.assertEqual(received[0]["session"], "waiting")
        self.assertEqual(received[0]["error"]["code"], "unreachable")
        self.assertEqual(json.loads(daemon.state_path().read_text())["session"], "waiting")


class _Collector:
    """Duck-typed subscriber queue: records instead of blocking."""

    def __init__(self, sink: list) -> None:
        self.sink = sink

    def put_nowait(self, item):
        self.sink.append(item)

    def get(self, timeout=None):        # pragma: no cover - not used here
        raise IndexError

    def __eq__(self, other):
        return self is other

    def __hash__(self):
        return id(self)


class Jobs(Base):
    def test_send_op_returns_frames(self):
        d = daemon.Daemon()
        pid = bytes.fromhex("00 10 24 06")
        fake = FakeBuds({CMD_INFO: [{"cmd": CMD_INFO | RESP_FLAG, "payload": pid}],
                         CMD_BATT_GET: [{"cmd": CMD_BATT_GET | RESP_FLAG,
                                         "payload": bytes.fromhex("00 01 01 32")}]})
        reply = d._run(fake, {"op": "send", "cmd": CMD_BATT_GET, "payload": ""})
        self.assertTrue(reply["ok"])
        self.assertEqual(reply["frames"], [{"cmd": CMD_BATT_GET | RESP_FLAG,
                                            "payload": "00010132"}])

    def test_push_inside_reply_window_is_not_swallowed(self):
        d = daemon.Daemon()
        d._product = "062410"
        push = {"cmd": 0x0204, "payload": bytes.fromhex("01 02 01 32 02 64")}
        ack = {"cmd": CMD_BATT_GET | RESP_FLAG, "payload": bytes.fromhex("00 01 01 32")}
        fake = FakeBuds({CMD_BATT_GET: [push, ack]})
        reply = d._run(fake, {"op": "send", "cmd": CMD_BATT_GET})
        self.assertEqual([f["cmd"] for f in reply["frames"]], [CMD_BATT_GET | RESP_FLAG])
        # the push is newer than the poll the reply answers, so it still owns
        # the snapshot (the reply must not undo it)
        self.assertEqual(d._snapshot()["battery"]["right"]["level"], 100)

    def test_client_battery_read_updates_the_snapshot(self):
        # A CLI `battery` through the daemon is device data: state.json must
        # not keep an old `updated` while handing out a fresh level.
        d = daemon.Daemon()
        fake = FakeBuds({CMD_BATT_GET: [
            {"cmd": CMD_BATT_GET | RESP_FLAG,
             "payload": bytes.fromhex("00 01 01 32")}]})
        before = d._snapshot()["updated"]
        reply = d._run(fake, {"op": "send", "cmd": CMD_BATT_GET})
        self.assertTrue(reply["ok"])
        state = json.loads(daemon.state_path().read_text())
        self.assertEqual(state["battery"]["left"]["level"], 50)
        self.assertIsNotNone(state["updated"])
        self.assertNotEqual(state["updated"], before)

    def test_game_command_clears_a_disagreeing_push(self):
        # The device only reports game mode with event 5, and only after a
        # gesture - a served command is not echoed, so a push from before it
        # must not stay in the snapshot as if it were current.
        d = daemon.Daemon()
        d._handle_event({"event_id": 5, "game": {"on": True, "state": 1}, "ts": 5})
        fake = FakeBuds({CMD_SWITCH_FEATURE: [
            {"cmd": CMD_SWITCH_FEATURE | RESP_FLAG, "payload": bytes([0])}]})
        reply = d._run(fake, {"op": "send", "cmd": CMD_SWITCH_FEATURE,
                              "payload": "0600"})
        self.assertTrue(reply["ok"])
        state = json.loads(daemon.state_path().read_text())
        self.assertIsNone(state["game"])
        self.assertEqual(state["updated"], 5)   # a command is not device data

    def test_game_command_keeps_an_agreeing_or_rejected_push(self):
        d = daemon.Daemon()
        pushed = {"on": True, "state": 1}
        d._handle_event({"event_id": 5, "game": pushed, "ts": 5})
        agree = FakeBuds({CMD_SWITCH_FEATURE: [
            {"cmd": CMD_SWITCH_FEATURE | RESP_FLAG, "payload": bytes([0])}]})
        d._run(agree, {"op": "send", "cmd": CMD_SWITCH_FEATURE, "payload": "0601"})
        self.assertEqual(d._snapshot()["game"], pushed)
        reject = FakeBuds({CMD_SWITCH_FEATURE: [
            {"cmd": CMD_SWITCH_FEATURE | RESP_FLAG, "payload": bytes([1])}]})
        d._run(reject, {"op": "send", "cmd": CMD_SWITCH_FEATURE, "payload": "0600"})
        self.assertEqual(d._snapshot()["game"], pushed)

    def test_unknown_op(self):
        d = daemon.Daemon()
        reply = d._run(FakeBuds(), {"op": "nope"})
        self.assertFalse(reply["ok"])
        self.assertEqual(reply["error"]["code"], "bad_request")


class Session(Base):
    def test_waiting_keeps_the_heartbeat_alive(self):
        # docs/daemon.md promises ts is rewritten at least every 60 s; a
        # reader (the widget) judges freshness on ts alone, so the back-off
        # path has to heartbeat too or a waiting daemon looks dead.
        d = daemon.Daemon(quiet=True)
        d.acquire_lock()
        self.addCleanup(d.release_lock)
        d.heartbeat = 0.05

        def hold():
            raise MelodyctlError("Host is down", code="unreachable")
        d._hold = hold
        thread = threading.Thread(target=d._session_loop, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 2.0)
        self.addCleanup(d.stop.set)

        def read_ts():
            try:
                return json.loads(daemon.state_path().read_text())["ts"]
            except (OSError, ValueError, KeyError):
                return None

        deadline = time.time() + 3.0
        first = None
        while first is None and time.time() < deadline:
            first = read_ts()
            time.sleep(0.02)
        self.assertIsNotNone(first)
        second = first
        while second <= first and time.time() < deadline:
            time.sleep(0.05)
            second = read_ts() or second
        self.assertGreater(second, first)

    def test_jobs_are_served_while_the_device_is_silent(self):
        # Regression: pushes are edge-triggered, and iter_events is a generator
        # that only returns from next() once it has an event - a loop that
        # drove the session through it answered clients only when the device
        # happened to push (observed: a 94 s stall on hardware).
        class Silent(FakeBuds):
            def notify_caps(self):
                return []

            def read_events(self, wait=1.0, oneplus_branch=False, product_id=None):
                time.sleep(0.02)
                return []

        pid = bytes.fromhex("00 10 24 06")
        fake = Silent({CMD_INFO: [{"cmd": CMD_INFO | RESP_FLAG, "payload": pid}],
                       CMD_BATT_GET: [{"cmd": CMD_BATT_GET | RESP_FLAG,
                                       "payload": bytes.fromhex("00 01 01 32")}]})
        d = daemon.Daemon(quiet=True)
        d.acquire_lock()
        self.addCleanup(d.release_lock)
        original = daemon.Buds
        daemon.Buds = lambda _addr: fake
        self.addCleanup(setattr, daemon, "Buds", original)
        thread = threading.Thread(target=d._hold, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 2.0)
        self.addCleanup(d.stop.set)

        started = time.time()
        reply = d._job({"op": "send", "cmd": CMD_BATT_GET})
        self.assertTrue(reply["ok"], reply)
        self.assertLess(time.time() - started, 5.0)

    def test_two_silent_polls_drop_the_session(self):
        # A bud that slept can leave the socket open and answer nothing; the
        # reply timeout is the only signal, so the session must be rebuilt.
        fake = self._silent_fake()
        d = daemon.Daemon(quiet=True, poll=0.1)
        d.acquire_lock()
        self.addCleanup(d.release_lock)
        original = daemon.Buds
        daemon.Buds = lambda _addr: fake
        self.addCleanup(setattr, daemon, "Buds", original)
        fake.replies[CMD_BATT_GET] = []          # seed and polls get nothing
        failures: list[BaseException] = []

        def hold():
            try:
                d._hold()
            except BaseException as exc:         # noqa: BLE001 - the assertion
                failures.append(exc)

        thread = threading.Thread(target=hold, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 3.0)
        thread.join(timeout=3.0)
        self.assertFalse(thread.is_alive(), "session never gave up")
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0].code, "disconnected")

    def _start_hold(self, fake, poll=120.0):
        d = daemon.Daemon(quiet=True, poll=poll)
        d.acquire_lock()
        self.addCleanup(d.release_lock)
        original = daemon.Buds
        daemon.Buds = lambda _addr: fake
        self.addCleanup(setattr, daemon, "Buds", original)
        thread = threading.Thread(target=d._hold, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 2.0)
        self.addCleanup(d.stop.set)
        return d

    def _wait_state(self, predicate, timeout=3.0):
        deadline = time.time() + timeout
        state = None
        while time.time() < deadline:
            try:
                state = json.loads(daemon.state_path().read_text())
            except (OSError, ValueError):
                state = None
            if state and predicate(state):
                return state
            time.sleep(0.02)
        self.fail(f"state never matched; last: {state}")

    def _silent_fake(self, battery_level=0x32):
        class Silent(FakeBuds):
            def notify_caps(self):
                return []

            def read_events(self, wait=1.0, oneplus_branch=False, product_id=None):
                time.sleep(0.02)
                return []

        pid = bytes.fromhex("00 10 24 06")
        return Silent({CMD_INFO: [{"cmd": CMD_INFO | RESP_FLAG, "payload": pid}],
                       CMD_BATT_GET: [{"cmd": CMD_BATT_GET | RESP_FLAG,
                                       "payload": bytes([0, 1, 1, battery_level])}]})

    def test_connect_seed_dates_the_battery_reading(self):
        # `updated` is "when the device last told us something". The seed read
        # counts, so a reconnect must not keep dating fresh levels to the last
        # push of a dead session (the widget shows "Updated Nm ago").
        d = self._start_hold(self._silent_fake())
        state = self._wait_state(lambda s: s["session"] == "connected")
        self.assertIsNotNone(state["updated"])
        self.assertEqual(state["battery"]["left"]["level"], 50)
        d.stop.set()

    def test_idle_link_is_polled_into_the_snapshot(self):
        # A quiet link still gets its battery refreshed (and the reply proves
        # the peer is alive - a slept bud can leave the socket open and silent).
        fake = self._silent_fake()
        d = self._start_hold(fake, poll=0.15)
        seeded = self._wait_state(lambda s: s["session"] == "connected")
        fake.replies[CMD_BATT_GET] = [{"cmd": CMD_BATT_GET | RESP_FLAG,
                                       "payload": bytes([0, 1, 1, 0x2A])}]
        polled = self._wait_state(
            lambda s: ((s.get("battery") or {}).get("left") or {}).get("level") == 42)
        self.assertGreater(polled["updated"], seeded["updated"])
        d.stop.set()


class Client(Base):
    def test_no_daemon_is_not_an_error(self):
        self.assertIsNone(remote.ping())
        with self.assertRaises(remote.NoDaemon):
            remote.request({"op": "ping"})

    def test_ping_and_send_over_a_socket(self):
        def handler(req, stream):
            if req["op"] == "ping":
                payload = {"ok": True, "addr": "AA:BB", "channel": 12,
                           "product": "062410", "session": "connected"}
            elif req["op"] == "send":
                payload = {"ok": True, "frames": [
                    {"cmd": int(req["cmd"]) | 0x8000, "payload": "00010132"}]}
            else:
                payload = {"ok": False, "error": {"code": "bad_request", "message": "no"}}
            stream.write((json.dumps(payload) + "\n").encode())
            stream.flush()

        server = FakeDaemon(handler)
        try:
            info = remote.ping()
            self.assertEqual(info["product"], "062410")
            conn = remote.RemoteBuds()
            conn.connect()
            self.assertEqual(conn.channel, 12)
            frames = conn.send_frames(CMD_BATT_GET)
            self.assertEqual(frames[0]["payload"], bytes.fromhex("00 01 01 32"))
            # the high-level API is inherited unchanged and just works
            self.assertEqual(conn.battery(), {"left": {"level": 50,
                                                       "charging": False}})
        finally:
            server.close()

    def test_socket_failure_falls_back(self):
        server = FakeDaemon(lambda req, s: None)
        server.close()                     # dead socket file left behind
        self.assertIsNone(remote.ping())


if __name__ == "__main__":
    unittest.main()
