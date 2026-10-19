# Open questions

Living list. Add a row when a question is raised; when answered, record it in
`claims-matrix.md` and mark it resolved here with a pointer. `[assumption]` is
allowed **only** in this file.

| id | question | why it matters | how to resolve | status |
|---|---|---|---|---|
| OQ-3 | Is ETI81's RFCOMM channel (12) discoverable via SDP? Prior art conflicts: osp54 says "12 exclusively", buildscript + Gazz use 15 on their devices | transport must not hardcode | probe discovery shipped (12 → 15 → 1..30, verified on ETI81, `--channel` override); SDP itself still unimplemented — resolve when a non-12-channel device is available | open (probe shipped) |
| OQ-6 | Does ANC query need auth (legacy HELLO + `0x8500` REGISTER token) on newer devices? | Phase 5 query design | prior-art cross-check; cannot test here. Our set path sends without the dance - if an ANC-device report shows sets failing, revisit | open |
| OQ-8 | Unknown unlocked commands: `0x0107 0x0109 0x0402 0x0408 0x0409 0x0416` (down from 8 — `0x0400` = find mode, `0x0405` = compactness detection, claims #31) | complete protocol coverage | the remaining six have no ack classifier in the app [apk:SetCommandStateInfo]; `0x0109` is sent by the app right after notification registration [apk:j#c] (candidate "initial state" query); otherwise need call-site analysis or device probes | open (partial 2026-10-17; `0x0109` lead 2026-10-19) |
| OQ-9 | Battery components beyond L/R/case on some models? | battery generalisation | whitelist + prior art | open — see OQ-12 |
| OQ-11 | What sets the battery `charging` bit? Every frame in runs 4-5 reported `charging: false`, including buds docked in the case at 80% and 100% | a widget should not show a charge bolt that never lights | dock the buds with the case on a charger and watch event `1` (needs a lid-open session); compare against the `0x0106` reply | open — no-heartbeat half resolved, see claims #43 |
| OQ-14 | When does the device send `0x8202` (the register-with-value frame the app routes to its event-2 handler with `arg1 = 33282`)? It never appeared on ETI81, across four re-registrations | the decoder has an untested path, and prior art's "0x8205 then 0x8204 snapshot" is unexplained | capture on a model that does send it, or find the device-side trigger in the app/other prior art | open |
| OQ-12 | Are component ids `1`/`2`/`3` universal, or do case-less/single-battery models use other ids? The app's vocabulary has `BatteryType.SINGLE` and 4 whitelist entries are neckbands (`type: N`) | battery/bud-status table correctness on those models | run `melodyctl watch --json` on a neckband or clip device — every decoded entry now keeps its raw id under `component` for exactly this | open |
| OQ-13 | Do the three clip entries really never push battery? They are the only whitelist entries without `function.batteryInfo` (OPPO Enco Clip/Clip2, OnePlus Buds Clip) | a widget must not show a stale `0%` there | `melodyctl report` + `watch` on one of them | open |

## Resolved

| id | answer | pointer |
|---|---|---|
| OQ-0 | `0x0105` is a component-version read, not EQ; CLI mislabel fixed in v1.2.2 | `docs/findings/2026-10-17-0x0105-is-remote-version.md` |
| OQ-1 | `0x010c` replies are type-tagged: `1`/`5` = bitmap window, `2` = level byte; ETI81's bare `02` has no window/value — decoded as "no noise-mode info", never a mode | claims #27/#28; `docs/protocol/commands/anc.md` |
| OQ-2 | Register style is chosen by capability: the app sends one `0x0205` when the device advertises it and otherwise one `0x0201` per event; ETI81's bitmap lacks group 22, so the app itself uses the per-event path we verify on hardware. `melodyctl watch` prefers bulk when advertised and falls back to per-event if no `0x8205` ack arrives | claims #7/#38; `docs/protocol/commands/notifications.md` |
| OQ-4 | Version kinds `1`/`2`/`3`/`4` = hardware / running firmware / backup / vendor code; the app displays running, else backup | claims #29; `docs/protocol/commands/version.md` |
| OQ-5 | Caps bitmap bit `i` = group `i` of the app's capability table; a group is a bundle of command ids (69 groups; ETI81 sets 12) and `DeviceInfo#getCapability` is exactly that flat id list | claims #30; `docs/protocol/commands/handshake.md` |
| OQ-7 | Feature-switch ids are device data: the app parses `(featureType, status)` pairs and echoes the advertised id — no id table exists in the APK; known ids listed in the command doc | claims #32; `docs/protocol/commands/feature-switch.md` |
| OQ-10 | All 85 whitelist entries advertise `supportSpp: true` — no BLE-only devices in this whitelist | `docs/devices/coverage.md` (generated) |
