# `0x0105` — component versions

- Direction: poll; request payload empty; response `0x8105`
  [hw:ETI81 2026-10-17].
- Response payload: `[status][count]`, then an ASCII CSV of `count` triples
  `(component, kind, value)` [hw:ETI81 2026-10-17] [prior:gazz@abe70f4].
- Components: `1` left, `2` right, `3` case [hw:ETI81 2026-10-17].
- `kind 2` = component firmware [hw:ETI81 2026-10-17] [prior:gazz@abe70f4].
- ETI81 (status `00`, count `09`): **left 165, right 165, case 118**
  [hw:ETI81 2026-10-17]; raw payload in
  [captures/2026-10-17-eti81-baseline.md](captures/2026-10-17-eti81-baseline.md).
- Same structure, independently confirmed against the phone's firmware
  display, on prior-art models: Buds Pro 541/541/510, Buds Pro 2 196/196/101
  [prior:gazz@abe70f4]. Left == right and the case differs in every capture so
  far, so `melodyctl fw` should generalise [untested].
- `kind 1` and `kind 4` records are returned but **not yet interpreted**
  (ETI81 kind 1 = 9/0/33, kind 4 = 0/0/0) → OQ-4.
- Prior-art parser note: firmware is formatted only when both left and right
  kind-2 records exist [prior:gazz@abe70f4].
- History: up to v1.2.1 this payload was mislabelled as "EQ presets"; fixed in
  v1.2.2 (`eq` → `fw`) [hw:ETI81 2026-10-17] (OQ-0).

See also: [commands/unmapped.md](unmapped.md) — EQ commands exist in prior art
but are not advertised on ETI81.
