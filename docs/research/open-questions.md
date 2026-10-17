# Open questions

Living list. Add a row when a question is raised; when answered, record it in
`claims-matrix.md` and mark it resolved here with a pointer. `[assumption]` is
allowed **only** in this file.

| id | question | why it matters | how to resolve | status |
|---|---|---|---|---|
| OQ-1 | What does `0x010c` returning bare `02` mean on ETI81? Unsupported code vs something else | ANC decoder must classify "no ANC" without inventing modes | APK cross-check; probe on an ANC device later | open (probe 2026-10-17) |
| OQ-2 | `0x0205` bulk subscribe vs our `0x0201` per-event register — are both valid family-wide? | notification flow generalisation | send `0x0205` on ETI81, capture `0x8205`; APK | open |
| OQ-3 | Is ETI81's RFCOMM channel (12) discoverable via SDP, or was it determined empirically? | transport must not hardcode; other devices may use 15 | `tools/rfcomm_scan.py` browse, save to captures | open |
| OQ-4 | Version-triple kinds 1 and 4 (ETI81: kind1 = 9/0/33, kind4 = 0/0/0) | complete version docs | APK; compare with other captures | open |
| OQ-5 | Caps bitmap decode — what do `ff 63` bits map to? | capability gating correctness | APK (`getRemoteCapability`), re-verify current unlocked list | open |
| OQ-6 | Does ANC query need auth (legacy HELLO + `0x8500` REGISTER token) on newer devices? | Phase 5 query design | prior-art cross-check; cannot test here | open |
| OQ-7 | `0x0403` feature ids beyond 6 (game mode) | feature-switch scope | APK feature table | open |
| OQ-8 | Unknown unlocked commands: `0x0107 0x0109 0x0400 0x0402 0x0405 0x0408 0x0409 0x0416` | complete protocol coverage | APK | open |
| OQ-9 | Battery components beyond L/R/case on some models? | battery generalisation | whitelist + prior art | open |
| OQ-10 | How many whitelist devices are SPP vs BLE-only (e.g. `supportSpp` false)? | honest v1 scope statement | count in `whitelist.json` | open |

## Resolved

| id | answer | pointer |
|---|---|---|
| OQ-0 | `0x0105` is a component-version read, not EQ; CLI mislabel fixed in v1.2.2 | `docs/findings/2026-10-17-0x0105-is-remote-version.md` |
