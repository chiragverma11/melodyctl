"""Golden push-event decoder tests (ETI81 captures, 2026-10-19).

Payloads recorded on OPPO Enco Buds (ETI81), product 062410 - see
`docs/protocol/captures/2026-10-19-eti81-notify-push.md`. The device pushed
these after `0x0200` + `0x0201` registration; nothing was polled.

Run: python3 -m unittest discover -s tests -t .
"""
import socket
import time
import unittest

from melodyctl import protocol as m
from melodyctl.errors import MelodyctlError
from melodyctl.transport import Buds

# 0x0204 type 1 (battery): 3 components, left 50%, right 80%, case 100%.
BATT_PUSH = bytes.fromhex("01 03 01 32 02 50 03 64")
# 0x0204 type 2 (bud status): left out of case, right in case, lid open.
STATUS_PUSH = bytes.fromhex("02 03 01 01 02 00 03 04")
# Same state, but the device listed right before left.
STATUS_PUSH_SWAPPED = bytes.fromhex("02 03 02 00 01 01 03 04")
# Lid closed, both buds in case.
STATUS_PUSH_CLOSED = bytes.fromhex("02 03 01 00 02 00 03 00")
# Synthetic: a bud seated in the ear (bit 1) while out of the case.
STATUS_PUSH_IN_EAR = bytes.fromhex("02 01 01 03")
# 0x0204 type 5 (game mode). Captured on ETI81: the body is `01 05 <state>`,
# so the state is body[2] there (run 7); other products read body[1].
GAME_PUSH_ETI81 = bytes.fromhex("05 01 05 01")   # 062410: ...state = 1 (on)
GAME_PUSH_GENERIC = bytes.fromhex("05 00 00")    # other products: body[1] = 0
# 0x0204 type 0xF2 (connected devices): one phone, connected 3 times.
# [count][mac6 reversed][connectTimes u16 LE][nameLen][name]
DEVICES_PUSH = bytes.fromhex("f2 01 05 04 03 02 01 00 03 00 0d 4f 6e 65 50 6c 75 73 20 39 20"
                             "50 72 6f")


class TestBatteryEvent(unittest.TestCase):
    def test_components_and_flags(self):
        self.assertEqual(m.decode_battery_event(BATT_PUSH[1:]), {
            "left": {"component": 1, "level": 50, "charging": False},
            "right": {"component": 2, "level": 80, "charging": False},
            "case": {"component": 3, "level": 100, "charging": False},
        })

    def test_charging_bit(self):
        # 0x81 = 1% and charging; 0x64 = 100% and not charging.
        self.assertEqual(m.decode_battery_event(bytes.fromhex("02 01 81 02 64")), {
            "left": {"component": 1, "level": 1, "charging": True},
            "right": {"component": 2, "level": 100, "charging": False},
        })

    def test_truncated_entry_is_dropped(self):
        self.assertEqual(m.decode_battery_event(bytes.fromhex("02 01 32 02")),
                         {"left": {"component": 1, "level": 50, "charging": False}})

    def test_unknown_component_keeps_its_id(self):
        # Case-less models are not guaranteed to use 1/2/3 [apk:BatteryType].
        self.assertEqual(m.decode_battery_event(bytes.fromhex("01 09 5A")),
                         {"id9": {"component": 9, "level": 90, "charging": False}})

    def test_empty(self):
        self.assertEqual(m.decode_battery_event(b""), {})


class TestStatusEvent(unittest.TestCase):
    def test_out_of_case_and_lid_open(self):
        # The case entry's in_case/in_ear bits are not meaningful - only
        # cover_open is; the decoder reports the raw flags for every entry.
        self.assertEqual(m.decode_status_event(STATUS_PUSH[1:]), {
            "left": {"component": 1, "in_case": False, "in_ear": False,
                     "cover_open": False, "safe_remind": False},
            "right": {"component": 2, "in_case": True, "in_ear": False,
                      "cover_open": False, "safe_remind": False},
            "case": {"component": 3, "in_case": True, "in_ear": False,
                     "cover_open": True, "safe_remind": False},
        })

    def test_component_order_is_not_significant(self):
        # The device listed right before left in one capture; results must agree.
        self.assertEqual(m.decode_status_event(STATUS_PUSH_SWAPPED[1:]),
                         m.decode_status_event(STATUS_PUSH[1:]))

    def test_lid_closed(self):
        st = m.decode_status_event(STATUS_PUSH_CLOSED[1:])
        self.assertFalse(st["case"]["cover_open"])
        self.assertTrue(st["left"]["in_case"] and st["right"]["in_case"])

    def test_in_ear_bit(self):
        # [apk:StatusInfo#<init>] bit 1 = in ear; not yet seen on ETI81 hardware.
        st = m.decode_status_event(STATUS_PUSH_IN_EAR[1:])
        self.assertTrue(st["left"]["in_ear"])
        self.assertFalse(st["left"]["in_case"])


class TestConnectedDevicesEvent(unittest.TestCase):
    def test_single_device(self):
        self.assertEqual(m.decode_connected_devices_event(DEVICES_PUSH[1:]), [{
            "address": "00:01:02:03:04:05",
            "connect_times": 3,
            "name": "OnePlus 9 Pro",
        }])

    def test_empty_and_truncated(self):
        self.assertEqual(m.decode_connected_devices_event(b""), [])
        self.assertEqual(m.decode_connected_devices_event(bytes.fromhex("01 00 01")), [])

    def test_two_devices(self):
        body = bytes([2]) + DEVICES_PUSH[2:] + bytes([0x05,4,3,2,1,0,1,0,2]) + b"PC"
        got = m.decode_connected_devices_event(body)
        self.assertEqual([d["address"] for d in got],
                         ["00:01:02:03:04:05", "00:01:02:03:04:05"])
        self.assertEqual([d["name"] for d in got], ["OnePlus 9 Pro", "PC"])
        self.assertEqual(got[1]["connect_times"], 1)


class TestGameModeEvent(unittest.TestCase):
    """Per-product offset for the game-mode status byte [apk:j#b]."""

    def test_eti81_reads_body_2(self):
        # captured frames: 05 01 05 01 (on) / 05 01 05 00 (off), run 7
        for pid in ("062410", "062810", "063410", "063010"):
            self.assertEqual(m.decode_game_mode_event(bytes.fromhex("01 05 01"), pid),
                             {"on": True, "state": 1}, pid)
            self.assertEqual(m.decode_game_mode_event(bytes.fromhex("01 05 00"), pid),
                             {"on": False, "state": 0}, pid)
            self.assertEqual(m.decode_game_mode_event(bytes.fromhex("01"), pid), {}, pid)

    def test_other_products_read_body_1(self):
        self.assertEqual(m.decode_game_mode_event(bytes([0x01, 1]), "06EC10"),
                         {"on": True, "state": 1})
        self.assertEqual(m.decode_game_mode_event(bytes([1]), None), {})
        self.assertEqual(m.decode_game_mode_event(b"", None), {})

    def test_product_id_case_insensitive(self):
        self.assertEqual(m.decode_game_mode_event(bytes.fromhex("01 05 01"), "062410".lower()),
                         {"on": True, "state": 1})


class TestRegisterPayload(unittest.TestCase):
    def test_bulk_register_payload(self):
        self.assertEqual(m.notify_register_payload([1, 2, 241, 242]),
                         bytes.fromhex("04 01 02 f1 f2"))

    def test_caps_gate_bulk_register(self):
        # ETI81: status 00 + bitmap ff 63 -> groups 0-9, 13, 14 only; the group
        # holding 0x0205 (bit 22) is beyond its 2-byte bitmap, so the app itself
        # registers per event there.
        self.assertNotIn(m.CMD_NOTIFY_REG_MULTI, m.decode_caps(bytes.fromhex("00 ff 63")))
        # bit 22 set -> 0x0205 is advertised.
        self.assertIn(m.CMD_NOTIFY_REG_MULTI,
                      m.decode_caps(bytes.fromhex("00 00 00 40")))


class TestNotifyDispatcher(unittest.TestCase):
    def test_battery_push(self):
        ev = m.decode_notify_event(BATT_PUSH)
        self.assertEqual(ev["event_id"], m.NOTIFY_BATTERY)
        self.assertEqual(ev["event"], "battery")
        self.assertEqual(ev["battery"]["right"]["level"], 80)

    def test_status_push(self):
        ev = m.decode_notify_event(STATUS_PUSH)
        self.assertEqual(ev["event"], "bud_status")
        self.assertFalse(ev["status"]["left"]["in_case"])

    def test_connected_devices_push(self):
        ev = m.decode_notify_event(DEVICES_PUSH)
        self.assertEqual(ev["event"], "connected_devices")
        self.assertEqual(ev["devices"][0]["name"], "OnePlus 9 Pro")

    def test_user_interaction_still_decodes(self):
        # [deviceType, button, action, function, scene] - gesture vocabulary.
        ev = m.decode_notify_event(bytes.fromhex("f1 01 01 02 01 00"))
        self.assertEqual(ev["event"], "user_interaction")
        self.assertEqual(ev["interaction"]["action"], 2)
        self.assertEqual(ev["interaction"]["function_name"], "play/pause")

    def test_unknown_event_keeps_raw_hex(self):
        ev = m.decode_notify_event(bytes.fromhex("07 aa bb"))
        self.assertEqual(ev["event"], "event7")
        self.assertEqual(ev["raw"], "AA BB")

    def test_game_mode_push_uses_product_offset(self):
        ev = m.decode_notify_event(GAME_PUSH_ETI81, product_id="062410")
        self.assertEqual(ev["event_id"], m.NOTIFY_GAME_MODE)
        self.assertEqual(ev["event"], "game_mode")
        self.assertTrue(ev["game"]["on"])
        # the same body on another product reads the leading byte instead
        ev = m.decode_notify_event(GAME_PUSH_GENERIC, product_id="06EC10")
        self.assertFalse(ev["game"]["on"])
    def test_empty_payload(self):
        self.assertEqual(m.decode_notify_event(b""), {})


class TestStatusFormatting(unittest.TestCase):
    def test_line(self):
        st = m.decode_status_event(STATUS_PUSH[1:])
        self.assertEqual(m._fmt_status(st),
                         "left=out-of-case  right=in-case  case=cover-open")

    def test_in_ear_line(self):
        st = m.decode_status_event(STATUS_PUSH_IN_EAR[1:])
        self.assertEqual(m._fmt_status(st), "left=in-ear")

    def test_unknown_component_is_named_not_dropped(self):
        st = m.decode_status_event(bytes.fromhex("01 09 01"))
        self.assertEqual(m._fmt_status(st), "id9=out-of-case")

    def test_battery_line_and_charging(self):
        self.assertEqual(
            m._fmt_battery(m.decode_battery_event(bytes.fromhex("01 01 81"))),
            "left=1%+")


class _FakeSock:
    """Minimal socket stand-in: recv() does what the test needs."""

    def __init__(self, recv):
        self._recv = recv
        self.closed = False

    def settimeout(self, _t):
        pass

    def recv(self, _n):
        return self._recv()

    def close(self):
        self.closed = True


class TestLinkLoss(unittest.TestCase):
    """The device closes the link when it idles or is cased; a watcher must
    find out instead of blocking on a socket that can never deliver again."""

    def _conn(self, sock) -> Buds:
        c = Buds()
        c.sock = sock
        return c

    def test_iter_events_raises_when_peer_closes(self):
        conn = self._conn(_FakeSock(lambda: b""))
        with self.assertRaises(MelodyctlError) as caught:
            next(conn.iter_events(0.05))
        self.assertEqual(caught.exception.code, "disconnected")
        self.assertIn("closed", str(caught.exception))

    def test_iter_events_raises_on_reset(self):
        def boom():
            raise OSError(104, "Connection reset by peer")
        conn = self._conn(_FakeSock(boom))
        with self.assertRaises(MelodyctlError) as caught:
            next(conn.iter_events(0.05))
        self.assertEqual(caught.exception.code, "disconnected")

    def test_timeouts_are_not_link_loss(self):
        # A quiet device is normal: socket.timeout keeps the loop waiting.
        calls = {"n": 0}

        def quiet():
            calls["n"] += 1
            if calls["n"] > 2:
                raise AssertionError("still looping, as expected")
            raise socket.timeout()
        conn = self._conn(_FakeSock(quiet))
        with self.assertRaises(AssertionError):
            next(conn.iter_events(0.05))

    def test_read_events_returns_when_the_device_is_quiet(self):
        # The daemon interleaves client requests between reads: a read must
        # come back even when no push arrives, or a silent device starves it.
        def quiet():
            raise socket.timeout()
        conn = self._conn(_FakeSock(quiet))
        started = time.time()
        self.assertEqual(conn.read_events(0.2), [])
        self.assertLess(time.time() - started, 1.0)

    def test_a_queued_push_is_delivered_before_the_error(self):
        # The peer can close right after a real push; the push must not be lost.
        frames = m.frame(m.CMD_NOTIFY_PUSH, BATT_PUSH, 0x30)
        sent = {"done": False}

        def once():
            if sent["done"]:
                raise OSError(32, "Broken pipe")
            sent["done"] = True
            return frames
        conn = self._conn(_FakeSock(once))
        it = conn.iter_events(0.05)
        ev = next(it)
        self.assertEqual(ev["battery"]["right"]["level"], 80)
        # The wire bytes and the frame that carried them ride along so a capture
        # can be re-verified (the two frame kinds decode identically).
        self.assertEqual(ev["hex"], BATT_PUSH.hex(" ").upper())
        self.assertEqual(ev["via"], "0x0204")
        with self.assertRaises(MelodyctlError):
            next(it)


if __name__ == "__main__":
    unittest.main()
