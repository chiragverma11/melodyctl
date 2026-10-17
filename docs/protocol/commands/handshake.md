# `0x0100` — capability handshake / hello

- Direction: poll; request payload empty; response `0x8100`
  [hw:ETI81 2026-10-17].
- Used as the connect hello: our CLI sends it and drains ~2 s before any other
  traffic [hw:ETI81 2026-10-17].
- Response payload: `[status][bitmap...]`; ETI81 answers `00 ff 63`
  [hw:ETI81 2026-10-17] (see
  [captures/2026-10-17-eti81-baseline.md](captures/2026-10-17-eti81-baseline.md)).
- Bitmap decode: bit `i` (LSB-first within each byte) selects group `i` of the
  app's `CAP_GROUPS` (`p026b8.a`), whose command ids are then unlocked
  [apk:p026b8.a]. ETI81's expansion is listed in [opo-v1.md](opo-v1.md).
- Which feature each group represents is **not yet interpreted** (OQ-5).
- No auth token: on ETI81 all reads and writes work with only this hello frame
  [hw:ETI81 2026-10-17].
- Prior art: newer devices require raw HELLO (`0x0001`) + REGISTER (`0x0085`,
  fixed four-byte token) with 2 s / 1.5 s waits before ANC writes
  [prior:gazz@abe70f4] [untested] → OQ-6.

Related: [transport.md](../transport.md) (session rules),
[opo-v1.md](../opo-v1.md) (master table).
