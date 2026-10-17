# OPPO Enco Buds (ETI81) — product `062410`

Status: **verified** (our hardware).

| field | value | tag |
|---|---|---|
| product id | `062410` (`0x0103` → `00 10 24 06`) | `[hw:ETI81 2026-10-17]` |
| whitelist | name "OPPO Enco Buds", brand `oppo`, type `T2` | `[wl:062410]` |
| firmware | 165 / 165 / 118 (left/right/case, kind-2 version records) | `[hw:ETI81 2026-10-17]` |
| transport | RFCOMM (SPP); channel 12 observed (discovery TBD → OQ-3); uuid `0000079A-D102-11E1-9B23-00025B00A5A5` | `[hw:ETI81]` `[wl:062410]` |
| caps bitmap | `00 ff 63` (bit mapping TBD → OQ-5) | `[hw:ETI81]` |
| ANC | none (whitelist; `0x010c` → `02`) | `[wl:062410]` `[hw:ETI81]` |
| EQ | none (whitelist; EQ commands not unlocked) | `[wl:062410]` |
| game mode | yes — `0x0403` feature 6 | `[hw:ETI81]` |
| gestures | read `0x0108`, write `0x0401`; observed: L double = prev, R double = next, both triple = game, L long = vol−, R long = vol+ | `[hw:ETI81]` |
| notifications | `0x0200` → `0x8200`, register `0x0201`, pushes `0x0204` (0xF1 = user tap) | `[hw:ETI81]` |
| battery | components 1/2/3 = L/R/case; right/case may be absent when idle | `[hw:ETI81]` |
| quirks | one RFCOMM connection at a time; drops to "Host is down" when idle (retry wakes it) | `[hw:ETI81]` |
