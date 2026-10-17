# `0x0100` — capability handshake / hello

- Direction: poll; request payload empty; response `0x8100`
  [hw:ETI81 2026-10-17].
- Used as the connect hello: our CLI sends it and drains ~2 s before any other
  traffic [hw:ETI81 2026-10-17].
- Response payload: `[status][bitmap...]`; ETI81 answers `00 ff 63`
  [hw:ETI81 2026-10-17] (see
  [captures/2026-10-17-eti81-baseline.md](captures/2026-10-17-eti81-baseline.md)).
- Bitmap decode: bit `i` (LSB-first within each byte) selects **group `i`** of
  the app's capability table (`p026b8.a`; transcribed below and as
  `CAP_GROUPS` in `melodyctl/protocol.py`); a set bit unlocks *every* command
  id in that group [apk:p026b8.a]. Groups bundle the commands the app gates
  together for one feature — e.g. group 8 = `0x010c` ANC query + `0x0404` ANC
  set, group 34 = `0x0122` custom-EQ read + `0x0418` custom-EQ write — and the
  app surfaces exactly this flat id list as capabilities
  (`DeviceInfo#getCapability(): List<Integer>` [apk:DeviceInfo#getCapability]),
  so the ids are the whole decode → OQ-5 resolved.
- ETI81's `ff 63` sets groups 0-9, 13, 14 → 15 command ids; that expansion is
  also listed in [opo-v1.md](opo-v1.md) [hw:ETI81 2026-10-17].
- No auth token: on ETI81 all reads and writes work with only this hello frame
  [hw:ETI81 2026-10-17].
- Prior art: newer devices require raw HELLO (`0x0001`) + REGISTER (`0x0085`,
  fixed four-byte token) with 2 s / 1.5 s waits before ANC writes
  [prior:gazz@abe70f4] [untested] → OQ-6.

## Capability groups

Bitmap bit = row (`p026b8.a` [apk:p026b8.a]). 69 groups exist; a 2-byte bitmap
addresses bits 0-15 only, and ETI81 only ever sets rows 0-9, 13 and 14. `—` =
app placeholder with no command ids. Note group 22 holds `0x0205`, the bulk
subscribe discussed in OQ-2 — beyond ETI81's 2-byte bitmap.

| group | unlocks | on ETI81 |
|---|---|---|
| 0 | 0x0105 | yes |
| 1 | 0x0106 | yes |
| 2 | 0x0107 | yes |
| 3 | 0x0108, 0x0401, 0x0416 | yes |
| 4 | 0x0109 | yes |
| 5 | 0x0400 | yes |
| 6 | 0x0402 | yes |
| 7 | 0x0403 | yes |
| 8 | 0x010c, 0x0404 | yes |
| 9 | 0x0405 | yes |
| 10 | 0x0406, 0x010f | |
| 11 | 0x0407 | |
| 12 | — | |
| 13 | 0x0408 | yes |
| 14 | 0x0409 | yes |
| 15 | — | |
| 16 | — | |
| 17 | 0x0114 | |
| 18 | — | |
| 19 | 0x040e, 0x040d, 0x0115, 0x0116 | |
| 20 | 0x040f | |
| 21 | 0x0410, 0x0119 | |
| 22 | 0x0205 | |
| 23 | 0x0f00 | |
| 24 | — | |
| 25 | 0x0118, 0x0411 | |
| 26 | 0x011a, 0x0412 | |
| 27 | 0x011c, 0x0413 | |
| 28 | — | |
| 29 | 0x0112, 0x040b | |
| 30 | 0x011e, 0x011f, 0x0415 | |
| 31 | 0x040d | |
| 32 | — | |
| 33 | 0x0121, 0x0417 | |
| 34 | 0x0122, 0x0418 | |
| 35 | 0x0419 | |
| 36 | 0x011d, 0x0414 | |
| 37 | 0x0123, 0x041a | |
| 38 | 0x0124, 0x041b | |
| 39 | 0x0125, 0x041c, 0x0127, 0x041d, 0x041f | |
| 40 | 0x0421, 0x0023, 0x0024, 0x0022, 0x0126, 0x0129 | |
| 41 | 0xef01 | |
| 42 | 0xef02 | |
| 43 | 0xef03, 0x041e | |
| 44 | 0x0420 | |
| 45 | 0x001c | |
| 46 | — | |
| 47 | 0x0422, 0x012a | |
| 48 | 0xef04 | |
| 49 | 0x0423, 0x012b | |
| 50 | — | |
| 51 | 0x0424 | |
| 52 | 0xef06 | |
| 53 | — | |
| 54 | — | |
| 55 | 0x0425, 0x012e, 0x0426 | |
| 56 | 0x012f | |
| 57 | 0x0427, 0x0130 | |
| 58 | 0x0131, 0x0428 | |
| 59 | 0x0429, 0x0132 | |
| 60 | 0x0014 | |
| 61 | 0x042d, 0x0133 | |
| 62 | 0x042e | |
| 63 | 0xef07 | |
| 64 | 0xef08, 0x0136, 0x0433 | |
| 65 | 0xef09 | |
| 66 | 0x0431, 0x0134 | |
| 67 | 0x0432, 0x0135, 0x0435 | |
| 68 | 0x0117 | |

Related: [transport.md](../transport.md) (session rules),
[opo-v1.md](../opo-v1.md) (master table).
