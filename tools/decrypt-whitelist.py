#!/usr/bin/env python3
"""Decrypt HeyMelody's bundled device whitelist (res/raw/heymelody_app_whitelist.json).

From com.oplus.melody.model.repository.whitelist.a and RepackagingDetector (U):
  key  = SHA-256 of the APK signing certificate (DER)
  data = AES-256-GCM (12-byte nonce) over a GZIP stream

Usage: decrypt-whitelist.py <apk> [out.json]
Requires: cryptography
"""
from __future__ import annotations

import gzip
import hashlib
import struct
import sys
import zipfile

from cryptography import x509
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def signing_cert_der(apk: str) -> bytes:
    """Extract the first X.509 signer certificate from the APK signing block."""
    data = open(apk, "rb").read()
    eocd = data.rfind(b"PK\x05\x06")
    cd_off = struct.unpack_from("<I", data, eocd + 16)[0]
    mpos = data.rfind(b"APK Sig Block 42", 0, cd_off)
    if mpos == -1:
        raise SystemExit("no APK signing block found")
    size = struct.unpack_from("<Q", data, mpos - 8)[0]
    p, end = mpos - size + 16, mpos - 8
    while p < end:
        ln = struct.unpack_from("<Q", data, p)[0]
        pid = struct.unpack_from("<I", data, p + 8)[0]
        val = data[p + 12:p + 8 + ln]
        if pid in (0x7109871A, 0xF05368C0):  # v2, v3
            for i in range(len(val) - 4):
                if val[i] == 0x30 and val[i + 1] == 0x82:
                    total = 4 + ((val[i + 2] << 8) | val[i + 3])
                    if i + total <= len(val):
                        try:
                            x509.load_der_x509_certificate(val[i:i + total])
                            return val[i:i + total]
                        except Exception:
                            pass
        p += 8 + ln
    raise SystemExit("no certificate found in signing block")


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    apk = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else "whitelist.json"
    key = hashlib.sha256(signing_cert_der(apk)).digest()
    blob = zipfile.ZipFile(apk).read("res/raw/heymelody_app_whitelist.json")
    plain = AESGCM(key).decrypt(blob[:12], blob[12:], None)
    data = gzip.decompress(plain)
    open(out, "wb").write(data)
    print(f"wrote {out} ({len(data)} bytes), key sha256={key.hex()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
