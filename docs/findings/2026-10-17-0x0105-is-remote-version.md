# 2026-10-17 — `0x0105` is a component-version read, not EQ

Device: OPPO Enco Buds (ETI81), product id `062410`.
Tool: `melodyctl` 1.2.1 module + ad-hoc probe (single RFCOMM session).

## Raw capture

Request: cmd `0x0105`, empty payload. Response payload:

```
00 09 31 2c 31 2c 39 2c 31 2c 32 2c 31 36 35 2c 31 2c 34 2c 30 2c
32 2c 31 2c 30 2c 32 2c 32 2c 31 36 35 2c 32 2c 34 2c 30 2c
33 2c 31 2c 33 33 2c 33 2c 32 2c 31 31 38 2c 33 2c 34 2c 30
```

ASCII: `1,1,9,1,2,165,1,4,0,2,1,0,2,2,165,2,4,0,3,1,33,3,2,118,3,4,0`

## Decoding

`status = 0x00`, `count = 9`, then 9 triples `(component, kind, value)`:

| component | kind 1 | kind 2 | kind 4 |
|---|---|---|---|
| 1 left | 9 | **165** | 0 |
| 2 right | 0 | **165** | 0 |
| 3 case | 33 | **118** | 0 |

Kind 2 = firmware. Left = right = 165, case = 118 — the same "buds equal, case
differs" pattern Gazz confirmed against phone UI for Buds Pro (`541.541.510`)
and Buds Pro 2 (`196.196.101`) `[prior:gazz]`.

## Impact

- v1.2.1 and earlier: `melodyctl eq` decoded this payload as "EQ presets" (groups
  of 9 numbers) and `eq-set` implied an EQ index write. Both are wrong for ETI81:
  the whitelist entry `062410` has no EQ and no EQ command is unlocked by caps.
  Fixed in v1.2.2: the read command is now `fw` (read-only); `eq-set` remains
  experimental and other-models-only.
- No plugin impact: the DMS widget calls only `battery --json`, `gestures --json`,
  `game`, `gesture-set` (checked 2026-10-17).
- Confirmation available: the phone's HeyMelody firmware display for this pair
  should read `165.165.118`.

## Follow-ups

- kinds 1 and 4 unexplained → OQ-4.
- Same probe: `0x0103` → `00 10 24 06` (id `062410`); `0x010c` → bare `02`;
  `0x0100` → `00 ff 63`. See `docs/protocol/captures/2026-10-17-eti81-baseline.md`.
