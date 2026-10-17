# `0x0103` — product id

- Direction: poll; request payload empty; response `0x8103`
  [hw:ETI81 2026-10-17].
- Response payload: `[status][id 3 bytes little-endian]`; ETI81 answers
  `00 10 24 06` → `062410` [hw:ETI81 2026-10-17] (see
  [captures/2026-10-17-eti81-baseline.md](captures/2026-10-17-eti81-baseline.md)).
- The id is the 6-hex-digit key into the HeyMelody whitelist
  (`compatWhiteList`, 85 devices); ETI81's entry is `062410` [wl:062410].
- Prior art agrees on the shape: status must be `0`, payload length 4, id
  formatted as `%06X` [prior:leaf@feb7b70]; Gazz refuses writes unless the id
  matches a known product profile [prior:gazz@abe70f4] [untested].
- Behaviour for ids not in the whitelist is **not yet interpreted**.

Related: [commands/handshake.md](handshake.md) (`0x0100` hello usually runs
first), [commands/version.md](version.md) (same session's version read).
