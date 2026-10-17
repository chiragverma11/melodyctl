# Protocol docs — index

Status: skeleton — Phase 2 fills the per-command docs. Until then, the legacy
single-file reference is `../protocol.md` plus the captures and findings.

Reading order: `transport` → `framing` → `opo-v1` (master table) → `commands/*`.

Evidence tags (see `AGENTS.md`): `[hw:ETI81 <date>]`, `[wl:<id>]`,
`[apk:<class#method>]`, `[prior:<project>@<sha>]`, `[untested]`, `[assumption]`.

| doc | status | content |
|---|---|---|
| `transport.md` | stub (P2) | SDP/RFCOMM discovery, UUIDs, channel, session lifetime |
| `framing.md` | stub (P2) | `AA \| LEN \| 00 00 \| cmd \| seq \| plen \| payload`, seq, resp `cmd\|0x8000`, reassembly quirks |
| `opo-v1.md` | stub (P2) | master command table (one row per command + evidence tag) |
| `commands/*.md` | stub (P2) | handshake, product-id, remote-version, battery, anc, feature-switch, gestures, notifications, batch-status |
| `captures/` | live | committed raw traces with provenance |

Known captures: `captures/2026-10-17-eti81-baseline.md`.
