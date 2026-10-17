# Protocol docs — index

Status: **live** (2026-10-17) — per-command docs are in place. The legacy
single-file reference is still `../protocol.md`.

Reading order: `transport` → `framing` → `opo-v1` (master table) → `commands/*`.

Evidence tags (see `AGENTS.md`): `[hw:ETI81 <date>]`, `[wl:<id>]`,
`[apk:<class#method>]`, `[prior:<project>@<sha>]`, `[untested]`, `[assumption]`.

| doc | status | content |
|---|---|---|
| [transport.md](transport.md) | live | SDP/RFCOMM discovery, UUIDs, channel, session lifetime |
| [framing.md](framing.md) | live | `AA \| LEN \| 00 00 \| cmd \| seq \| plen \| payload`, seq, resp `cmd\|0x8000`, length quirks |
| [opo-v1.md](opo-v1.md) | live | master command table + ETI81 caps bitmap |
| [commands/handshake.md](commands/handshake.md) | live | `0x0100` capability / hello |
| [commands/product-id.md](commands/product-id.md) | live | `0x0103` product id |
| [commands/version.md](commands/version.md) | live | `0x0105` component versions |
| [commands/battery.md](commands/battery.md) | live | `0x0106` battery |
| [commands/anc.md](commands/anc.md) | live | `0x010c` query, `0x0404` set |
| [commands/gestures.md](commands/gestures.md) | live | `0x0108` read, `0x0401` write |
| [commands/feature-switch.md](commands/feature-switch.md) | live | `0x0403` `[featureId, enable]` |
| [commands/notifications.md](commands/notifications.md) | live | `0x0200` / `0x0201` / `0x0204` (+ `0x0205`) |
| [commands/unmapped.md](commands/unmapped.md) | live | unlocked-but-uninterpreted, not-advertised commands |
| [captures/](captures/) | live | committed raw traces with provenance |

Known captures: `captures/2026-10-17-eti81-baseline.md`.
