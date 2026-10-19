# `0x0106` — battery

- Direction: poll; request payload empty; response `0x8106`
  [hw:ETI81 2026-10-17].
- Response payload: `[00][count]` then `count` pairs `[component, raw]`
  [hw:ETI81 2026-10-17].
- `raw & 0x7f` = percentage; bit 7 (`0x80`) = charging
  [hw:ETI81 2026-10-17] [prior:gazz@abe70f4] [prior:leaf@feb7b70].
- Components: `1` left, `2` right, `3` case [apk:C0922j]
  [prior:leaf@feb7b70] [prior:gazz@abe70f4].
- ETI81 quirk: while idle, the right and/or case entries may be absent from
  the reply [hw:ETI81 2026-10-17].
- Prior-art variation: the Buds Pro prefixes the pairs with a one-byte
  component count; Gazz's parser accepts count-prefixed or pair-only payloads
  [prior:gazz@abe70f4] [untested].
- The same body is **pushed** as event `1` of `0x0204`, with the event id where
  the `0x8106` reply has its status byte [hw:ETI81 2026-10-19]: subscribe with
  `0x0200` + `0x0201` and the device reports changes on its own. Prior art
  documented the shape first [prior:leaf@feb7b70] [prior:gazz@abe70f4].
  One push carries every component, and charging is bit 7 of the same byte
  [hw:ETI81 2026-10-19]; see [commands/notifications.md](notifications.md).
- Pushes are **edge-triggered with no heartbeat**, and the case entry is
  dropped while both buds are out — poll with `0x0106` when you need a value
  now [hw:ETI81 2026-10-19].
- Component ids `1`/`2`/`3` read as left/right/case, but the app's vocabulary
  includes a single-battery kind (`BatteryType.SINGLE`), so case-less models
  are not guaranteed to use them [apk:BatteryType] → OQ-12.

Related: `melodyctl battery`, `monitor`, `watch`; JSON output keeps a flat
`{left,right,case}` map for widgets.
