# OPOv1 — master command table (HeyMelody family)

`AA`-framed little-endian commands over RFCOMM (see [framing.md](framing.md)).
Only ETI81 is verified by us. Status legend:

- **verified** — run on ETI81 hardware [hw:ETI81 2026-10-17]
- **unlocked, not interpreted** — bitmap-advertised but no documented
  behaviour (OQ-8)
- **not advertised** — caps bitmap says no on ETI81
- **prior** — prior-art evidence only, not tested by us [untested]

| cmd | dir | ETI81 status | doc |
|---|---|---|---|
| `0x0100` | poll | verified — hello/caps; replies `00 ff 63` | [commands/handshake.md](commands/handshake.md) |
| `0x0103` | poll | verified — `00 10 24 06` → `062410` | [commands/product-id.md](commands/product-id.md) |
| `0x0105` | poll | verified — 165/165/118 | [commands/version.md](commands/version.md) |
| `0x0106` | poll | verified | [commands/battery.md](commands/battery.md) |
| `0x0107` | poll | unlocked, not interpreted | [commands/unmapped.md](commands/unmapped.md) |
| `0x0108` | poll | verified | [commands/gestures.md](commands/gestures.md) |
| `0x0109` | poll | unlocked, not interpreted | [commands/unmapped.md](commands/unmapped.md) |
| `0x010c` | poll | verified query; ETI81 bare `02` = no bitmap (type-tagged, OQ-1 resolved) | [commands/anc.md](commands/anc.md) |
| `0x010d` | poll | not advertised; prior only [prior:gazz@abe70f4] [prior:leaf@feb7b70] | [commands/unmapped.md](commands/unmapped.md) |
| `0x0200` | write | verified — replies the pushable event ids `01 02 F1 F2` | [commands/notifications.md](commands/notifications.md) |
| `0x0201` | write | verified — per-event register; app fallback when `0x0205` is unsupported (OQ-2 resolved) | [commands/notifications.md](commands/notifications.md) |
| `0x8202` | push | device-initiated register-with-value; read as `[status][eventId][body]` [apk:j#c] | [commands/notifications.md](commands/notifications.md) |
| `0x0204` | push | verified — `payload[0]` = event id; `1` battery, `2` bud status, `0xF1` user interaction | [commands/notifications.md](commands/notifications.md) |
| `0x0205` | write | app uses it for bulk register when the device supports it [apk:j#c]; not sent by us | [commands/notifications.md](commands/notifications.md) |
| `0x0400` | write | unlocked; app name **find mode** (find earbuds); payload not documented [apk:SetCommandStateInfo#isFindModeRsp] | [commands/unmapped.md](commands/unmapped.md) |
| `0x0401` | write | verified — ack `0`/`1` | [commands/gestures.md](commands/gestures.md) |
| `0x0402` | write | unlocked, not interpreted | [commands/unmapped.md](commands/unmapped.md) |
| `0x0403` | write | verified — feature 6 = game mode | [commands/feature-switch.md](commands/feature-switch.md) |
| `0x0404` | write | unlocked; ETI81 has no ANC; mechanism prior only [prior:leaf@feb7b70] | [commands/anc.md](commands/anc.md) |
| `0x0405` | write | unlocked; app name **compactness detection** (fit detection); payload not documented [apk:SetCommandStateInfo#isCompactnessDetectRsp] | [commands/unmapped.md](commands/unmapped.md) |
| `0x0406` | write | not advertised (no EQ); prior only [prior:leaf@feb7b70] [prior:gazz@abe70f4] | [commands/unmapped.md](commands/unmapped.md) |
| `0x0408` | write | unlocked, not interpreted | [commands/unmapped.md](commands/unmapped.md) |
| `0x0409` | write | unlocked, not interpreted | [commands/unmapped.md](commands/unmapped.md) |
| `0x0416` | write | unlocked, not interpreted | [commands/unmapped.md](commands/unmapped.md) |
| `0x0423` | write | not advertised on ETI81 | [commands/unmapped.md](commands/unmapped.md) |
| `0x0f00` | write | not advertised (debug group 23); app name switch debug [apk:SetCommandStateInfo#isSwitchDebugRsp] | [commands/unmapped.md](commands/unmapped.md) |

## Capability bitmap (`0x0100` reply)

ETI81 replies `00 ff 63`: status `00` + bitmap `ff 63` [hw:ETI81 2026-10-17].

The bitmap indexes `CAP_GROUPS` (`p026b8.a`) and unlocks the command ids it
names [apk:p026b8.a]. As currently documented, ETI81's bitmap unlocks:

```
0x0105 0x0106 0x0107 0x0108 0x0109 0x010c 0x0400 0x0401
0x0402 0x0403 0x0404 0x0405 0x0408 0x0409 0x0416
```

[hw:ETI81 2026-10-17]

- `0x0100`, `0x0103` and the `0x02xx` notification family are not gated by the
  bitmap; they work regardless [hw:ETI81 2026-10-17].
- The bitmap is a list of capability-table indexes (bit `i` = group `i`); a
  group bundles the command ids the app unlocks together (often a feature's
  read + write pair). Full 69-group table in
  [commands/handshake.md](commands/handshake.md) (OQ-5 resolved).
- There is no auth token on ETI81: reads and writes work with only the hello
  frame [hw:ETI81 2026-10-17]; newer-device auth is prior art only → OQ-6.
