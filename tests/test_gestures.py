"""Gesture vocabulary: presets, product branch, whitelist slot validation.

Tables come from the HeyMelody APK (see docs/protocol/commands/gestures.md,
tags `[apk:Ha.a#b]`, `[apk:Ha.a#c]`, `[apk:Ha.a#g]`) and the decrypted
whitelist's per-device `function.control` masks.
"""
import unittest

from melodyctl import devices
from melodyctl.protocol import decode_gestures, function_name, mask_wires, preset_wire


class PresetTable(unittest.TestCase):
    def test_wire_codes(self):
        for bit, code in ((0x200, 0), (0x4, 1), (0x2, 2), (0x1, 3),
                          (0x400, 7), (0x80, 8), (0x100, 9), (0x800, 10),
                          (0x8, 11), (0x10, 12), (0x1000, 13), (0x2000, 17),
                          (0x10000, 18), (0x8000, 22), (0x20000, 25),
                          (0x100000, 26), (0x200000, 26), (0x40000, 28),
                          (0x80000, 29), (0x800000, 32), (0x1000000, 34),
                          (0x2000000, 35)):
            self.assertEqual(preset_wire(bit), code, hex(bit))

    def test_not_settable_as_functions(self):
        # enter pairing / clear pairing history have no wire code in Ha.a#b
        self.assertIsNone(preset_wire(0x4000))
        self.assertIsNone(preset_wire(0x400000))

    def test_oneplus_branch_shift(self):
        self.assertEqual(preset_wire(0x20), 5)
        self.assertEqual(preset_wire(0x40), 6)
        self.assertEqual(preset_wire(0x20, True), 4)
        self.assertEqual(preset_wire(0x40, True), 5)
        self.assertEqual(function_name(5), "previous song")
        self.assertEqual(function_name(5, True), "next song")


class MaskTables(unittest.TestCase):
    def test_eti81_masks(self):
        p = devices.profile_for("062410")
        self.assertEqual(mask_wires(devices.gesture_slot(p, 1, 1)["support"]), [0, 1])
        self.assertEqual(mask_wires(devices.gesture_slot(p, 1, 2)["support"]), [0, 1, 5, 6])
        self.assertEqual(mask_wires(devices.gesture_slot(p, 1, 3)["support"]), [0, 3, 17])
        self.assertEqual(mask_wires(devices.gesture_slot(p, 1, 4)["support"]), [0, 11, 12])

    def test_x4_pinch_and_slide(self):
        p = devices.profile_for("06EC10")
        self.assertFalse(devices.oneplus_branch(p))
        self.assertEqual(mask_wires(devices.gesture_slot(p, 1, 16)["support"]), [0, 1, 34])
        self.assertEqual(mask_wires(devices.gesture_slot(p, 1, 17)["support"]),
                         [0, 1, 5, 6, 3, 32, 17])
        self.assertEqual(mask_wires(devices.gesture_slot(p, 1, 5)["support"]), [0, 7, 10])
        self.assertIsNone(devices.gesture_slot(p, 1, 20).get("support"))

    def test_bullets_z3_button_five(self):
        p = devices.profile_for("051014")
        self.assertEqual([s.get("button") for s in devices.gesture_slots(p)], [5] * 4)
        self.assertIsNone(devices.gesture_slot(p, 1, 1))  # advertised on button 5 only
        self.assertEqual(mask_wires(devices.gesture_slot(p, 5, 1)["support"]), [1])

    def test_oneplus_buds_branch(self):
        p = devices.profile_for("060414")
        self.assertTrue(devices.oneplus_branch(p))
        mask = devices.gesture_slot(p, 1, 2)["support"]
        self.assertEqual(mask_wires(mask), [1, 5, 6, 3])
        self.assertEqual(mask_wires(mask, True), [1, 4, 5, 3])


class Decode(unittest.TestCase):
    def test_names_with_branch(self):
        # left double tap -> previous song (f5) on ETI81
        rows = decode_gestures(bytes.fromhex("00 01 01 01 02 05"))
        self.assertEqual(rows[0]["action_name"], "double tap")
        self.assertEqual(rows[0]["function_name"], "previous song")
        # the same frame through the OnePlus branch: f5 means next song
        rows = decode_gestures(bytes.fromhex("00 01 01 01 02 05"), True)
        self.assertEqual(rows[0]["function_name"], "next song")


class WriteChecks(unittest.TestCase):
    """cli._gesture_write_problems: device-driven combo validation."""

    @staticmethod
    def _args(**kw):
        import argparse
        base = dict(ear=1, button=1, action=2, function=5)
        base.update(kw)
        return argparse.Namespace(**base)

    def test_eti81_combos(self):
        from melodyctl import cli
        p = devices.profile_for("062410")
        self.assertEqual(cli._gesture_write_problems(p, self._args(action=2, function=5)), [])
        problems = cli._gesture_write_problems(p, self._args(action=2, function=3))
        self.assertTrue(problems and "allows" in problems[0])

    def test_unadvertised_action(self):
        from melodyctl import cli
        p = devices.profile_for("062410")
        problems = cli._gesture_write_problems(p, self._args(action=16, function=1))
        self.assertTrue(problems and "does not advertise" in problems[0])

    def test_unknown_device_skips(self):
        from melodyctl import cli
        self.assertEqual(cli._gesture_write_problems(None, self._args()), [])

    def test_button_five_required_on_z3(self):
        from melodyctl import cli
        p = devices.profile_for("051014")
        self.assertTrue(cli._gesture_write_problems(p, self._args(action=1, function=1)))
        self.assertEqual(
            cli._gesture_write_problems(p, self._args(button=5, action=1, function=1)), [])


class Profiles(unittest.TestCase):
    def test_gesture_tables_present(self):
        covered = [p for p in devices.PROFILES.values() if devices.gesture_slots(p)]
        self.assertEqual(len(covered), 83)

    def test_caps_summary_mentions_gestures(self):
        summary = devices.caps_summary(devices.profile_for("062410"))
        self.assertIn("gestures(4)", summary)


if __name__ == "__main__":
    unittest.main()
