"""Golden push-event decoder tests (ETI81 captures, 2026-10-19).

Payloads recorded on OPPO Enco Buds (ETI81), product 062410 - see
`docs/protocol/captures/2026-10-19-eti81-notify-push.md`. The device pushed
these after `0x0200` + `0x0201` registration; nothing was polled.

Run: python3 -m unittest discover -s tests -t .
"""
import unittest

from melodyctl import protocol as m

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


class TestBatteryEvent(unittest.TestCase):
    def test_components_and_flags(self):
        self.assertEqual(m.decode_battery_event(BATT_PUSH[1:]), {
            "left": {"level": 50, "charging": False},
            "right": {"level": 80, "charging": False},
            "case": {"level": 100, "charging": False},
        })

    def test_charging_bit(self):
        # 0x81 = 1% and charging; 0x64 = 100% and not charging.
        self.assertEqual(m.decode_battery_event(bytes.fromhex("02 01 81 02 64")), {
            "left": {"level": 1, "charging": True},
            "right": {"level": 100, "charging": False},
        })

    def test_truncated_entry_is_dropped(self):
        self.assertEqual(m.decode_battery_event(bytes.fromhex("02 01 32 02")),
                         {"left": {"level": 50, "charging": False}})

    def test_empty(self):
        self.assertEqual(m.decode_battery_event(b""), {})


class TestStatusEvent(unittest.TestCase):
    def test_out_of_case_and_lid_open(self):
        # The case entry's in_case/in_ear bits are not meaningful - only
        # cover_open is; the decoder reports the raw flags for every entry.
        self.assertEqual(m.decode_status_event(STATUS_PUSH[1:]), {
            "left": {"in_case": False, "in_ear": False,
                     "cover_open": False, "safe_remind": False},
            "right": {"in_case": True, "in_ear": False,
                      "cover_open": False, "safe_remind": False},
            "case": {"in_case": True, "in_ear": False,
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


if __name__ == "__main__":
    unittest.main()
