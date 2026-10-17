"""Golden decoder tests from ETI81 captures (2026-10-17).

Payloads recorded on OPPO Enco Buds (ETI81), product 062410 - see
`docs/protocol/captures/2026-10-17-eti81-baseline.md`. These are the regression
fixtures for the Phase 4 package refactor; keep them verbatim.

Run: python3 -m unittest discover -s tests -t .
"""
import unittest

import melodyctl as m

CAPS_PAYLOAD = bytes.fromhex("00 ff 63")
VERSION_PAYLOAD = bytes.fromhex(
    "00 09 31 2c 31 2c 39 2c 31 2c 32 2c 31 36 35 2c 31 2c 34 2c 30 2c"
    "32 2c 31 2c 30 2c 32 2c 32 2c 31 36 35 2c 32 2c 34 2c 30 2c"
    "33 2c 31 2c 33 33 2c 33 2c 32 2c 31 31 38 2c 33 2c 34 2c 30")
INFO_PAYLOAD = bytes.fromhex("00 10 24 06")
ANC_PROBE_PAYLOAD = bytes.fromhex("02")


class TestFraming(unittest.TestCase):
    def test_frame_bytes(self):
        # cmd 0x0106 (battery), seq 0x20, empty payload
        self.assertEqual(m.frame(0x0106, b"", 0x20),
                         bytes.fromhex("aa 07 00 00 06 01 20 00 00"))

    def test_roundtrip(self):
        frames = m.parse_frames(m.frame(0x0106, b"\x01\x02", 0x21))
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0]["cmd"], 0x0106)
        self.assertEqual(frames[0]["payload"], b"\x01\x02")

    def test_concatenated_frames(self):
        two = m.frame(0x0100, b"", 1) + m.frame(0x8106, b"\x00\x01\x01\x50", 2)
        self.assertEqual([f["cmd"] for f in m.parse_frames(two)], [0x0100, 0x8106])


class TestDecoders(unittest.TestCase):
    def test_caps_eti81(self):
        # captured bitmap `ff 63` -> the documented unlocked command set
        self.assertEqual(m.decode_caps(CAPS_PAYLOAD), {
            0x105, 0x106, 0x107, 0x108, 0x109, 0x10c,
            0x400, 0x401, 0x402, 0x403, 0x404, 0x405, 0x408, 0x409, 0x416})

    def test_version_records_eti81(self):
        recs = m.decode_version_records(VERSION_PAYLOAD)
        self.assertEqual(len(recs), 9)  # count=9 triples
        self.assertEqual(recs[1], {"component": 1, "kind": 2, "value": 165})
        self.assertEqual(recs[4], {"component": 2, "kind": 2, "value": 165})
        self.assertEqual(recs[7], {"component": 3, "kind": 2, "value": 118})

    def test_fw_string(self):
        recs = m.decode_version_records(VERSION_PAYLOAD)
        self.assertEqual(m._fmt_versions(recs), "left=165  right=165  case=118")

    def test_version_malformed(self):
        self.assertEqual(m.decode_version_records(b""), [])
        self.assertEqual(m.decode_version_records(b"\x00"), [])

    def test_product_id_little_endian(self):
        # `00 10 24 06` -> status + 3-byte LE id `10 24 06` -> 062410
        self.assertEqual(INFO_PAYLOAD[1:][::-1].hex(), "062410")

    def test_anc_probe_is_bare_byte(self):
        # ETI81: 0x010c answers one byte, no ANC bitmap (open question OQ-1)
        self.assertEqual(ANC_PROBE_PAYLOAD, b"\x02")


if __name__ == "__main__":
    unittest.main()
