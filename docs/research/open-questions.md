# Open questions

Living list. Add a row when a question is raised; when answered, record it in
`claims-matrix.md` and mark it resolved here with a pointer. `[assumption]` is
allowed **only** in this file.

| id | question | why it matters | how to resolve | status |
|---|---|---|---|---|
| OQ-1 | What does `0x010c` returning bare `02` mean on ETI81? Unsupported code vs something else | ANC decoder must classify "no ANC" without inventing modes | APK cross-check; probe on an ANC device later | open (probe 2026-10-17) |
| OQ-2 | `0x0205` bulk subscribe vs our `0x0201` per-event register — are both valid family-wide? | notification flow generalisation | Gazz: `0x0200`→`0x8200`, then `0x0205` with the exact advertised set → `0x8205` + `0x0204` snapshot (`[prior:gazz@abe70f4]`, no `0x0201` involved); ours (`0x0201`) works on ETI81 — test `0x0205` on ETI81; APK | open |
| OQ-3 | Is ETI81's RFCOMM channel (12) discoverable via SDP? Prior art conflicts: osp54 says "12 exclusively", buildscript + Gazz use 15 on their devices | transport must not hardcode | probe discovery shipped (12 → 15 → 1..30, verified on ETI81, `--channel` override); SDP itself still unimplemented — resolve when a non-12-channel device is available | open (probe shipped) |
| OQ-4 | Version-triple kinds 1 and 4 (ETI81: kind1 = 9/0/33, kind4 = 0/0/0) | complete version docs | APK; compare with other captures | open |
| OQ-5 | Caps bitmap decode — what do `ff 63` bits map to? | capability gating correctness | APK (`getRemoteCapability`), re-verify current unlocked list | open |
| OQ-6 | Does ANC query need auth (legacy HELLO + `0x8500` REGISTER token) on newer devices? | Phase 5 query design | prior-art cross-check; cannot test here. Our set path sends without the dance - if an ANC-device report shows sets failing, revisit | open |
| OQ-7 | `0x0403` feature ids beyond 6 (game mode) | feature-switch scope | APK feature table | open |
| OQ-8 | Unknown unlocked commands: `0x0107 0x0109 0x0400 0x0402 0x0405 0x0408 0x0409 0x0416` | complete protocol coverage | APK | open |
| OQ-9 | Battery components beyond L/R/case on some models? | battery generalisation | whitelist + prior art | open |
| OQ-10 | How many whitelist devices are SPP vs BLE-only? | honest v1 scope statement | answered 2026-10-17: all 85 advertise SPP | **resolved** |

## Resolved

| id | answer | pointer |
|---|---|---|
| OQ-0 | `0x0105` is a component-version read, not EQ; CLI mislabel fixed in v1.2.2 | `docs/findings/2026-10-17-0x0105-is-remote-version.md` |
| OQ-10 | All 85 whitelist entries advertise `supportSpp: true` — no BLE-only devices in this whitelist | `docs/devices/coverage.md` (generated) |
