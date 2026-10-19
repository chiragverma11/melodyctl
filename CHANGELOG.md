# Changelog

All notable changes to this project are documented here. This project adheres
to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- `melodyctl watch` decodes the device's own pushes: `0x0204` event `1` prints as
  `BATTERY left=50% right=80% case=100%` and event `2` as
  `STATUS left=out-of-case right=in-case case=cover-open` (gestures unchanged,
  anything else as raw hex). New `--json` (one object per event, for daemons and
  widgets) and `-e/--events` (register only the listed ids the device advertises).
- `watch` also decodes event `242` (`0xF2`) as
  `DEVICES 00:01:02:03:04:05 x3 OnePlus 9 Pro` (the app's connected-device
  list), every battery/status entry now keeps its raw component id under
  `component` (case-less models are not guaranteed to use left/right/case), and
  each event carries a timestamp - `[HH:MM:SS]` in the human line, `ts` in JSON.
- `watch --json` events carry their evidence: `hex` (the wire payload) and `via`
  (the frame that carried it, e.g. `0x0204`), so a capture can be re-verified
  and `0x0204` pushes can be told apart from `0x8202` register values. Under
  `--json` all human chatter now goes to stderr, leaving stdout a pure JSON
  stream.
- Registration now mirrors the app: one bulk `0x0205` when the device's
  capability bitmap advertises it, otherwise one `0x0201` per advertised id,
  with an automatic fall back to `0x0201` when the bulk register is refused.
  ETI81 advertises neither, so its verified path is unchanged (a forced
  `0x0205` there is ignored outright, which the fallback absorbs).

### Changed
- Gesture support is now one-to-one with HeyMelody across the family:
  `profiles.json` carries every device's `function.control` slots (83/85
  entries; actions up to 27, `button: 5` on the Bullets Wireless Z3), and
  `gesture-set` validates the requested combo against the *connected* device's
  support masks before writing (the ETI81 checks are now generated from the
  same data). The full preset/action/button vocabulary from the app is
  documented in `docs/protocol/commands/gestures.md`.

### Fixed
- `melodyctl watch` no longer hangs silently when the earbuds disconnect (they do
  when they idle or go back in the case with the lid shut): the dead socket is
  detected and reported as one clean `disconnected` line instead of waiting
  forever on a link that can never deliver again. New `--reconnect` waits for the
  buds at startup and rebuilds the session after each drop. Verified on ETI81
  across three lid-close/reopen cycles.
- Docs: the claim that the case entry is "always present" in push frames was
  wrong — it holds while a bud is in the case, but the device drops component
  `3` from both events once **both** buds are out (claims #44, corrected in
  `docs/protocol/captures/2026-10-19-eti81-notify-push.md`).
- Gesture naming corrected against the HeyMelody app: function code 2 is
  "listening music" (was `resume`), 26/27 are AI translation variants, 32 is
  "spy tap"; button 6 means the neckband volume-key pair (the old
  "slide/pinch group / actions 28-37" claim was wrong - pinch is actions
  16-20), and the misleading `button=long` alias is gone.

### Documentation
- CLI help, README, daemon and tools wording now present the tool as
  HeyMelody-family; the `gesture-set` tables now list the family vocabulary
  and note that per-device combos are checked against the connected device.
- README restructured for visitors: install + quick start first, full command
  table, explicit verification ladder, linked `dms-plugins` widget section, and
  corrected daemon instructions. Whitelist/APK regeneration moved to
  `AGENTS.md`.
- Open-question closures from the HeyMelody APK: `0x010c` replies are
  type-tagged and ETI81's bare `02` is not a mode (OQ-1), version kinds 1-4 are
  hardware/running/backup/vendorCode (OQ-4), caps bits are capability-table
  group indexes with the full 69-group table now in
  `docs/protocol/commands/handshake.md` (OQ-5), and feature-switch ids are
  device data rather than app constants (OQ-7); `0x0400` is find mode and
  `0x0405` is compactness detection (OQ-8 partial). Details:
  `docs/research/open-questions.md`.
- Push channel documented from hardware: capture
  `docs/protocol/captures/2026-10-19-eti81-notify-push.md`, rewritten
  `docs/protocol/commands/notifications.md` (app event table, battery and
  bud-status layouts, status-flag bits, component-order and always-present-case
  caveats, `0x8202` register-with-value, `batteryRadix` note); OQ-2 resolved
  (`0x0201` per-event is the family-safe register path) and `0x0109` noted as
  the app's post-registration command (OQ-8).

## [1.3.0] - 2026-10-17

### Added
- `melodyctl device` - identify the connected earbuds (0x0103 product id, whitelist name, brand, capabilities, verification status).
- `melodyctl report` - read-only, sanitised compatibility report (product id, caps bitmap, firmware, battery, raw ANC probe, transport channel); `--with-addr` opts into the Bluetooth address.
- Channel discovery: connect probes 12 -> 15 -> 1..30 when no channel is known (stdlib has no SDP) and sticks with the first that accepts; `--channel` / `MELODYCTL_CHANNEL` override.
- Write gating: `game`, `eq-set` and `gesture-set` verify the product id via 0x0103 and refuse writes on non-verified profiles unless `--force` (new `--force` on `game` and `eq-set`).
- `melodyctl anc` - show noise-cancelling state (0x010c) and `anc set <mode>` built from the device's whitelist mode table (bit = protocolIndex; names from modeType), verified by re-query; gated like other writes and untested without ANC hardware.

### Changed
- Package refactor: the single-file CLI is now `melodyctl/` (`protocol`,
  `transport`, `errors`, `cli`) with `melodyctl.py` kept as a shim for running
  from a checkout; the installed console script is unchanged. No behaviour
  change - golden decoder tests still pass. Device profiles generated from the
  HeyMelody whitelist ship as package data (`melodyctl/data/profiles.json`).

## [1.2.2] - 2026-10-17

### Fixed
- `eq` misread `0x0105`: it is not an EQ table. The payload is `status`,
  `count`, then ASCII triples `(component, kind, value)` where kind 2 is the
  component firmware. The command is now `fw` (left/right/case firmware), with
  `--raw` and `--json` showing all records. ETI81 has no EQ - `0x0406` is not
  advertised by the device; `eq-set` stays for other models (experimental).

## [1.2.1] - 2026-10-16

### Fixed
- Ctrl-C (`SIGINT`) now exits quietly with status 130 instead of printing a
  `KeyboardInterrupt` traceback (visible in `monitor` and `watch`).

## [1.2.0] - 2026-10-16

### Added
- Machine-readable errors: with `--json`, a failure prints a single JSON object
  on stderr - `{"error":{"code","message","hint"}}`. Codes: `busy`, `refused`,
  `unreachable`, `no_adapter`, `timeout`, `no_bluetooth_support`, `error`.

### Changed
- No more tracebacks: every exception is reported as one clean `error:` line
  (plus a `hint:` line when known). Set `MELODYCTL_DEBUG=1` to see the traceback.
  This lets the DMS widget/settings show a short message instead of raw stderr.

## [1.1.1] - 2026-10-16

### Added
- Clear error when run on a Python without `socket.AF_BLUETOOTH` (uv's managed
  CPython builds lack it).

### Changed
- Recommend `uv tool install --python /usr/bin/python3 ...`; pipx kept as an
  alternative. (uv now manages the CLI alongside other tools.)

## [1.1.0] - 2026-10-16

### Added
- `melodyctl --version` / `-V`.

### Changed
- Document installing as a command with
  `pipx install git+https://github.com/chiragverma11/melodyctl`.

## [1.0.0] - 2026-10-16

First release. Verified on the **OPPO Enco Buds (ETI81)**.

### Added
- `melodyctl battery` - individual Left / Right / Case battery levels (with
  `--json` for widgets and `--json-full` including charging flags).
- `melodyctl monitor` - continuous battery polling.
- `melodyctl caps` - decode the device capability bitmap (`0x0100`).
- `melodyctl gestures` - read the touch-gesture (key function) table.
- `melodyctl gesture-set` - assign a gesture function, with value tables
  (`--list`), human-friendly names, pre-flight validation and `--force`.
- `melodyctl game on|off` - toggle low-latency game mode (`0x0403`, feature 6).
- `melodyctl watch` - subscribe to device events and live-map tapped gestures.
- `melodyctl raw` - send a raw OPOv1 packet.
- `daemon/melodyctl-daemon.py` + systemd user unit to publish battery as JSON.
- `tools/decrypt-whitelist.py` to decrypt HeyMelody's bundled device whitelist.

### Notes
- Protocol: OPOv1 over Bluetooth Classic RFCOMM (SPP), the same wire protocol
  HeyMelody uses for OPPO/OnePlus SPP earbuds. Only ETI81 is verified.
- EQ is read-only and noise reduction is not exposed on ETI81. **Corrected in 1.2.2:** ETI81 has no EQ at all - the old `eq` command read component versions (`0x0105`).
