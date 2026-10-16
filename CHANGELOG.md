# Changelog

All notable changes to this project are documented here. This project adheres
to [Semantic Versioning](https://semver.org/).

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
- EQ is read-only and noise reduction is not exposed on ETI81.
