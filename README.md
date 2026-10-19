# melodyctl

Control **HeyMelody-family earbuds** (OPPO Enco, OnePlus Buds) from Linux over
the same wire protocol HeyMelody uses: per-ear battery, touch gestures, game
mode, noise cancelling (on ANC models), and live button events. No Android app,
no BLE pairing dance - just Bluetooth Classic RFCOMM.

> **Verification:** hardware-verified on one device so far - the **OPPO Enco Buds
> (ETI81, whitelist id `062410`)**. Profiles for the other 84 whitelist models
> ship `[untested]`: reads run on any of them, write commands are gated unless
> `--force`, and `melodyctl report` is the fact-collection path for upgrading a
> model. See [Devices & verification](#devices--verification) and
> [Limitations](#limitations).

## Install

Requires Linux with BlueZ (buds **paired** and connectable), Python 3.10+, and
your buds' Bluetooth address - set `MELODYCTL_ADDR` or pass `--addr` (the
built-in default is the maintainer's test unit). Only one RFCOMM connection at a
time.

```bash
# install as a command (recommended) -> provides `melodyctl` on PATH
uv tool install --python /usr/bin/python3 git+https://github.com/chiragverma11/melodyctl

# pin a release (append @vX.Y.Z to the URL)
uv tool install --python /usr/bin/python3 "git+https://github.com/chiragverma11/melodyctl@v1.5.0"

# alternatives
pipx install git+https://github.com/chiragverma11/melodyctl   # pipx also works
python3 melodyctl.py --help                                   # or just run it in place
```

> **Use a system Python.** `melodyctl` needs `socket.AF_BLUETOOTH`, which uv's
> *managed* CPython builds omit - hence `--python /usr/bin/python3` above. If you
> see `this Python has no Bluetooth socket support`, reinstall with a system
> interpreter.

## Quick start

```bash
export MELODYCTL_ADDR=AA:BB:CC:DD:EE:FF   # your earbuds (or pass --addr)

melodyctl device                          # identify: product id -> whitelist profile
melodyctl battery                         # Left 80%  Right 100%  Case 70%
melodyctl battery --json                  # {"left":80,"right":100,"case":70}
melodyctl fw                              # component / firmware versions
melodyctl gestures                        # current touch-gesture table
melodyctl gesture-set --list              # every valid ear/button/action/function value
melodyctl gesture-set -l --json -p 062410 # ...machine-readable, + that model's allowed combos
melodyctl game on                         # low-latency mode
melodyctl anc                             # noise-cancelling state (ANC models)
melodyctl watch                           # live battery, case/bud state, gestures, connected devices
```

`gesture-set` accepts names or numbers and validates the combination before
sending:

```bash
melodyctl gesture-set left  tap single play/pause
melodyctl gesture-set right tap triple game      # game mode on triple-tap
melodyctl gesture-set both  tap long   vol+      # both ears, hold = volume up
```

## Commands

| Command | Does |
|---|---|
| `melodyctl battery` | Left / Right / Case levels (`--json`, `--json-full`) |
| `melodyctl monitor` | Poll battery continuously (`-i` interval) |
| `melodyctl caps` | Decode the capability bitmap + unlocked command ids |
| `melodyctl device` | Identify the connected model (product id → whitelist profile) |
| `melodyctl report` | Read-only compatibility report, paste-safe (`--with-addr` includes the address) |
| `melodyctl fw` | Component / firmware versions (`--raw`, `--json`) |
| `melodyctl anc` | Show noise-cancelling state; `anc set <mode>` on ANC models |
| `melodyctl gestures` | Read the touch-gesture table |
| `melodyctl gesture-set` | Assign a gesture function (`--list` for values; `--list --json [--product ID]` for the machine-readable vocabulary + that model's allowed combos, offline) |
| `melodyctl game on\|off` | Toggle low-latency game mode |
| `melodyctl watch` | Live-subscribe to the device's pushes: battery, case/bud state, gestures, game mode, connected devices - timestamped lines, or one JSON object per event with a `ts` field (`--json`); `--reconnect` waits for the buds and reconnects after they drop (`--retry-max` caps the back-off, `-f` registers unadvertised ids for probing) |
| `melodyctl raw` | Send a raw OPOv1 packet (debugging) |
| `melodyctl daemon` | Hold the RFCOMM link, publish `state.json` and serve commands ([docs/daemon.md](docs/daemon.md)) |

`devinfo` (raw hex dump) and `eq-set` (EQ preset by protocol index,
experimental) exist for edge use - `melodyctl --help` lists everything.
Commands use a running `melodyctl daemon` when there is one and open their own
session when there is not; `--no-daemon` forces the direct session.

## Devices & verification

melodyctl targets the whole HeyMelody family. Device profiles are generated from
the official HeyMelody whitelist (85 models) and ship inside the CLI.

| level | meaning |
|---|---|
| `verified` | run on real hardware by this project, captured in `docs/` |
| `external` | a named third party's published evidence |
| `untested` | whitelist-derived (`[untested]`); may work, may not |

Today **1 of 85 models is verified** - the OPPO Enco Buds (ETI81). Reads
(battery, `caps`, `gestures`, `fw`, `anc` query) run on any whitelist model;
write commands (`gesture-set`, `game`, `eq-set`, `anc set`) check the product id
and refuse unverified models unless `--force` is passed. The full matrix lives in
[docs/devices/coverage.md](docs/devices/coverage.md).

Owning another model? Run `melodyctl report` and open an issue with the JSON -
that is exactly what is needed to upgrade its row to `verified`.

## Desktop widget

A **DankMaterialShell** (Quickshell) widget lives in the
[`dms-plugins`](https://github.com/chiragverma11/dms-plugins/tree/main/melodyctl)
repo. It shows the battery in the bar, refreshes on open, and has a popout with
the gesture table and game-mode toggle; the title shows the model actually
connected (via `melodyctl device`). With a `melodyctl daemon` running it reads
push state instead - battery, charging, bud/lid state and game mode update as
the buds report them, without the widget opening a connection of its own. With
no daemon it polls `melodyctl battery --json-full`, exactly as before. It finds
`melodyctl` on `PATH`, or you can point it at a script path in its settings.

## Daemon (optional)

The device allows one RFCOMM connection at a time, and its pushes are
edge-triggered (reconnecting re-sends nothing), so a link held open is the
freshest data source there is. `melodyctl daemon` holds it and publishes:

- `$XDG_RUNTIME_DIR/melodyctl/state.json` - battery, case/bud state and game
  mode as they are pushed, with a `session` field to gate on;
- `$XDG_RUNTIME_DIR/melodyctl/daemon.sock` - commands and the live event
  stream, for the CLI and for widgets.

Full contract: [docs/daemon.md](docs/daemon.md).

```bash
melodyctl daemon                 # foreground, Ctrl-C to stop
cat "$XDG_RUNTIME_DIR/melodyctl/state.json"

# or as a systemd user unit:
git clone https://github.com/chiragverma11/melodyctl   # or use your existing checkout
mkdir -p ~/.config/systemd/user
cp melodyctl/daemon/melodyctl-daemon.service ~/.config/systemd/user/

# edit the unit first:
#   ExecStart=                     -> `command -v melodyctl` (uv tool installs to ~/.local/bin)
#   Environment=MELODYCTL_ADDR=... -> your earbuds' address

systemctl --user daemon-reload
systemctl --user enable --now melodyctl-daemon
journalctl --user -u melodyctl-daemon -f
```

Nothing auto-starts it and nothing supervises it: with no daemon running, every
command opens its own session exactly as before.

## Errors

Failures print as a **single line** (never a Python traceback), plus a `hint:`
line when known. With `--json` they become a machine-readable object on stderr:

```bash
$ melodyctl battery --json
{"error": {"code": "unreachable", "message": "Host is down", "hint": "The earbuds are unreachable (off or out of range)."}}
```

Codes: `busy` (another app holds the link), `refused`, `unreachable`,
`no_adapter` (Bluetooth off), `timeout`, `no_channel` (no RFCOMM channel
accepted), `no_bluetooth_support` (wrong Python), `error`. Set
`MELODYCTL_DEBUG=1` to get the full traceback.

## How it works

The buds speak **OPOv1** over Bluetooth Classic RFCOMM (SPP). Frames are
`AA | LEN | 00 00 | cmd_lo cmd_hi | seq | plen_lo plen_hi | payload` (little
endian, response `cmd | 0x8000`). Battery is command `0x0106`; gestures are
`0x0108` (read) / `0x0401` (write); game mode is the feature switch `0x0403`
with feature id `6`. See [docs/protocol/](docs/protocol/index.md) for the
per-command reference.

## Limitations

- **Verification, not capability:** only 1 of the 85 whitelist models is
  hardware-verified; everything else is `[untested]` profile data (reads open,
  writes gated). Feature support (ANC, EQ, slide/pinch) varies by model - the
  per-device rows are in [docs/devices/coverage.md](docs/devices/coverage.md).
- The `anc set` write path has not been exercised on ANC hardware; it is
  whitelist-derived and verified by re-query after each write.
- Channel discovery is probe-based (12 → 15 → 1..30) because the Python stdlib
  has no SDP; `--channel` / `MELODYCTL_CHANNEL` override it.
- Firmware flashing is intentionally out of scope.

## Repository layout

| path | what |
|---|---|
| `melodyctl/` | the CLI package: `protocol`, `transport`, `cli`, generated profiles in `data/` |
| `melodyctl.py` | thin shim so `python3 melodyctl.py ...` works from a checkout |
| `docs/` | protocol + device documentation - the project's source of truth |
| `daemon/` | optional battery daemon + systemd unit |
| `tools/` | probes, whitelist decrypt, profile generator (maintainer) |
| `whitelist.json` | decrypted HeyMelody device whitelist (85 devices) |

## License

[MIT](LICENSE). Not affiliated with or endorsed by OPPO / HeyTap. "OPPO",
"Enco" and "HeyMelody" are trademarks of their respective owners.
