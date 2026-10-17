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
- Unsolicited battery reports (`0x0204`, type `0x01`, count + pairs) are
  documented by prior art [prior:leaf@feb7b70] [untested]; not observed on
  ETI81 — see [commands/notifications.md](notifications.md) for `0x0204`.

Related: `melodyctl battery`, `monitor`; JSON output keeps a flat
`{left,right,case}` map for widgets.
