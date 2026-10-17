# Notifications — `0x0200` / `0x0201` / `0x0204` (and `0x0205`)

## Advertise (`0x0200` → `0x8200`)

- No payload; response `[status][count][eventId...]`
  [hw:ETI81 2026-10-17].
- ETI81 advertises `[1, 2, 241, 242]` [hw:ETI81 2026-10-17]. `241` (`0xF1`) =
  user interaction; ids 1/2/242 are **not yet interpreted**.
- Same shape in prior art, different id sets: Buds Pro `01 02 03 04 06 08 0a`,
  Buds Pro 2 ten codes including `f1 f2 f3` [prior:gazz@abe70f4]
  [prior:leaf@feb7b70].

## Register (`0x0201` → `0x8201`)

- Payload `[eventId]`; works on ETI81 [hw:ETI81 2026-10-17] — our CLI
  registers each advertised id and reads the per-event status byte
  (payload[0]).
- Prior art never used `0x0201`: they sent bulk `0x0205` with the exact
  advertised set → `0x8205` (per-code status echo) followed immediately by a
  `0x0204` snapshot [prior:gazz@abe70f4]. Which flow is family-valid is
  **OQ-2**.

## Pushes (`0x0204`)

- `payload[0]` = event id [hw:ETI81 2026-10-17].
- `0xF1` (241) = user interaction; body is
  `[deviceType, button, action, function, scene]` [hw:ETI81 2026-10-17] — same
  field vocabulary as [commands/gestures.md](gestures.md).
- Prior art reads `0x0204` as a multiplex: type `0x01` battery, `0x03` ANC
  change, `0x04` fit detection, `0x06` connected-device list
  [prior:leaf@feb7b70] [untested] — that numbering does not match ETI81's
  advertised ids, so do not merge the two tables.
- Prior-art discipline worth keeping: subscribe only to advertised codes and
  never treat unknown/unsolicited payloads as state proof
  [prior:gazz@abe70f4].

Related: `melodyctl watch` (subscribes and prints decoded events),
[opo-v1.md](../opo-v1.md).
