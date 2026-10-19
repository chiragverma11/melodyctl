# Open questions

Living list. Add a row when a question is raised; when answered, record it in
`claims-matrix.md` and mark it resolved here with a pointer. `[assumption]` is
allowed **only** in this file.

| id | question | why it matters | how to resolve | status |
|---|---|---|---|---|
| OQ-3 | Is ETI81's RFCOMM channel (12) discoverable via SDP? Prior art conflicts: osp54 says "12 exclusively", buildscript + Gazz use 15 on their devices | transport must not hardcode | probe discovery shipped (12 → 15 → 1..30, verified on ETI81, `--channel` override); SDP itself still unimplemented — resolve when a non-12-channel device is available | open (probe shipped) |
| OQ-6 | Does ANC query need auth (legacy HELLO + `0x8500` REGISTER token) on newer devices? | Phase 5 query design | prior-art cross-check; cannot test here. Our set path sends without the dance - if an ANC-device report shows sets failing, revisit | open |
| OQ-8 | Unknown unlocked commands: `0x0107 0x0109 0x0402 0x0408 0x0409 0x0416` (down from 8 — `0x0400` = find mode, `0x0405` = compactness detection, claims #31) | complete protocol coverage | the remaining six have no ack classifier in the app [apk:SetCommandStateInfo]; `0x0109` is sent by the app right after notification registration [apk:j#c] (candidate "initial state" query); otherwise need call-site analysis or device probes | open (partial 2026-10-17; `0x0109` lead 2026-10-19) |
| OQ-9 | Battery components beyond L/R/case on some models? | battery generalisation | whitelist + prior art | open |

## Resolved

| id | answer | pointer |
|---|---|---|
| OQ-0 | `0x0105` is a component-version read, not EQ; CLI mislabel fixed in v1.2.2 | `docs/findings/2026-10-17-0x0105-is-remote-version.md` |
| OQ-1 | `0x010c` replies are type-tagged: `1`/`5` = bitmap window, `2` = level byte; ETI81's bare `02` has no window/value — decoded as "no noise-mode info", never a mode | claims #27/#28; `docs/protocol/commands/anc.md` |
| OQ-2 | Both register styles exist: `0x0201` per event (what we send) and `0x0205` bulk; the app picks `0x0205` only when the device advertises it and falls back to `0x0201` otherwise, so per-event registration is the family-wide-safe path | claims #7; `docs/protocol/commands/notifications.md` |
| OQ-4 | Version kinds `1`/`2`/`3`/`4` = hardware / running firmware / backup / vendor code; the app displays running, else backup | claims #29; `docs/protocol/commands/version.md` |
| OQ-5 | Caps bitmap bit `i` = group `i` of the app's capability table; a group is a bundle of command ids (69 groups; ETI81 sets 12) and `DeviceInfo#getCapability` is exactly that flat id list | claims #30; `docs/protocol/commands/handshake.md` |
| OQ-7 | Feature-switch ids are device data: the app parses `(featureType, status)` pairs and echoes the advertised id — no id table exists in the APK; known ids listed in the command doc | claims #32; `docs/protocol/commands/feature-switch.md` |
| OQ-10 | All 85 whitelist entries advertise `supportSpp: true` — no BLE-only devices in this whitelist | `docs/devices/coverage.md` (generated) |
