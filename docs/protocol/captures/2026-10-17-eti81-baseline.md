# Capture — ETI81 baseline probes (2026-10-17)

Device: OPPO Enco Buds (ETI81) · product id `062410` · firmware 165/165/118
Tool: `melodyctl` 1.2.1 module, one RFCOMM session. `seq` varies per request.

Payloads below are as decoded by `parse_frames` (frame header stripped).

| cmd | request payload | response payload (hex) | notes |
|---|---|---|---|
| `0x0100` caps | — | `00 ff 63` | status `00` + bitmap `ff 63` |
| `0x0103` info | — | `00 10 24 06` | status `00` + 3-byte LE id → `062410` |
| `0x0105` version | — | `00 09 31 2c … 2c 30` | ASCII CSV, see `docs/findings/2026-10-17-0x0105-is-remote-version.md` |
| `0x010c` ANC query | `01 01` | `02` | single byte, no ANC bitmap → OQ-1 |

Full `0x0105` payload (hex):

```
00 09 31 2c 31 2c 39 2c 31 2c 32 2c 31 36 35 2c 31 2c 34 2c 30 2c
32 2c 31 2c 30 2c 32 2c 32 2c 31 36 35 2c 32 2c 34 2c 30 2c
33 2c 31 2c 33 33 2c 33 2c 32 2c 31 31 38 2c 33 2c 34 2c 30
```

ASCII: `1,1,9,1,2,165,1,4,0,2,1,0,2,2,165,2,4,0,3,1,33,3,2,118,3,4,0`
