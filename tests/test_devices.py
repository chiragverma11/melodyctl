"""Device profiles, write gating, product-id decode (stdlib unittest)."""
import unittest

from melodyctl import devices
from melodyctl.protocol import decode_caps, decode_product_id


class ProfileDb(unittest.TestCase):
    def test_whitelist_loaded(self):
        self.assertEqual(len(devices.PROFILES), 85)

    def test_eti81_profile(self):
        p = devices.profile_for("062410")
        self.assertIsNotNone(p)
        self.assertEqual(p["name"], "OPPO Enco Buds")
        self.assertEqual(p["brand"], "oppo")
        self.assertTrue(devices.is_verified("062410"))
        self.assertEqual(devices.caps_summary(p), ["battery", "game-mode", "gestures(4)"])

    def test_unknown_and_empty(self):
        self.assertIsNone(devices.profile_for("ffffff"))
        self.assertIsNone(devices.profile_for(None))
        self.assertFalse(devices.is_verified("ffffff"))
        self.assertFalse(devices.is_verified(None))

    def test_write_gate_reasons(self):
        self.assertIsNone(devices.write_refusal("062410", "gesture"))
        self.assertIn("untested profile", devices.write_refusal("063C14", "gesture"))
        self.assertIn("whitelist", devices.write_refusal("ffffff", "gesture"))
        self.assertIn("identity", devices.write_refusal(None, "gesture"))


class IdAndCaps(unittest.TestCase):
    def test_product_id(self):
        self.assertEqual(decode_product_id(bytes.fromhex("00 10 24 06")), "062410")
        self.assertIsNone(decode_product_id(b"\x00\x01\x02"))
        self.assertIsNone(decode_product_id(b""))

    def test_eti81_caps_map(self):
        cmds = decode_caps(bytes.fromhex("00 ff 63"))
        self.assertIn(0x0105, cmds)     # fw read unlocked
        self.assertIn(0x0404, cmds)     # ANC set unlocked (device has no ANC)
        self.assertNotIn(0x0406, cmds)  # EQ set not advertised


if __name__ == "__main__":
    unittest.main()
