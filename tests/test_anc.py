"""ANC bit math + whitelist mode tables (stdlib unittest)."""
import unittest

from melodyctl import devices
from melodyctl.protocol import anc_bitmap, decode_anc_bitmap


class Bitmap(unittest.TestCase):
    def test_leaf_examples(self):
        self.assertEqual(anc_bitmap(0), b"\x01")
        self.assertEqual(anc_bitmap(4), b"\x10")
        self.assertEqual(anc_bitmap(7), b"\x80")
        self.assertEqual(anc_bitmap(9), b"\x00\x02")

    def test_lowest_bit(self):
        self.assertEqual(decode_anc_bitmap(b"\x02"), 1)
        self.assertEqual(decode_anc_bitmap(b"\x00\x02"), 9)
        self.assertEqual(decode_anc_bitmap(b"\x30"), 4)
        self.assertIsNone(decode_anc_bitmap(b"\x00"))
        self.assertIsNone(decode_anc_bitmap(b""))


class ModeTables(unittest.TestCase):
    def test_enco_x4_table(self):
        p = devices.profile_for("06EC10")
        self.assertIsNotNone(p)
        bits = {m["protocol_index"] for m in devices.anc_modes(p)}
        for bit in (0, 1, 2, 3, 4, 5, 6, 7, 8, 11, 12, 13, 14):
            self.assertIn(bit, bits)
        m = devices.anc_mode_for_bit(p, 4)
        self.assertEqual(m["mode_type"], 4)

    def test_eti81_has_no_anc(self):
        p = devices.profile_for("062410")
        self.assertEqual(devices.anc_modes(p), [])
        self.assertIsNone(devices.anc_mode_for_bit(p, 1))
        self.assertEqual(devices.anc_modes(None), [])
        self.assertIsNone(devices.anc_mode_for_bit(None, 0))


if __name__ == "__main__":
    unittest.main()
