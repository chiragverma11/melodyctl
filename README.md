# melodyctl

Control **HeyMelody-family earbuds** (OPPO Enco, OnePlus Buds) from Linux over
the same wire protocol HeyMelody uses: read per-ear battery, read/write touch
gestures, toggle game mode, switch noise cancelling on ANC models, and watch
for button events. No Android app, no BLE pairing dance - just Bluetooth
Classic RFCOMM.

> **Scope:** hardware-verified only on the **OPPO Enco Buds (ETI81 / whitelist
> id `062410`)**. Device profiles for 85 HeyMelody models ship in the CLI
> (whitelist-derived, `[untested]`); reads work on any of them, write commands
> are gated to verified profiles unless `--force` is passed, and
> `melodyctl report` is the fact-collection path for upgrading a model - see
> [Limitations](#limitations).

## What you get

| Command | Does |
|---|---|
| `melodyctl battery` | Left / Right / Case levels (`--json`, `--json-full`) |
| `melodyctl monitor` | Poll battery continuously |
| `melodyctl caps` | Decode the device capability bitmap |
| `melodyctl device` | Identify the connected device (product id → whitelist profile) |
| `melodyctl report` | Read-only compatibility report, paste-safe (`--with-addr` includes the address) |
| `melodyctl anc` | Show noise-cancelling state; `anc set <mode>` on ANC models |
| `melodyctl gestures` | Read the touch-gesture table |
| `melodyctl gesture-set` | Assign a gesture function |
| `melodyctl game on\|off` | Toggle low-latency game mode |
| `melodyctl watch` | Live-map gestures as you tap the buds |
| `melodyctl raw` | Send a raw OPOv1 packet |

## Requirements

- Linux with BlueZ (the buds must be **paired** and connectable)
- Python 3.10+
- Your buds' Bluetooth address (defaults to `6C:0D:E1:5F:DB:4D`; override with
  `MELODYCTL_ADDR` or `--addr`)

Only one RFCOMM connection is allowed at a time.

## Install

```bash
# install as a command (recommended) -> provides `melodyctl` on PATH
uv tool install --python /usr/bin/python3 git+https://github.com/chiragverma11/melodyctl

# alternatives
pipx install git+https://github.com/chiragverma11/melodyctl   # pipx also works
python3 melodyctl.py --help                                   # or just run it in place
```

> **Use a system Python.** `melodyctl` needs `socket.AF_BLUETOOTH`, which uv's
> *managed* CPython builds omit - hence `--python /usr/bin/python3` above. If you
> see `this Python has no Bluetooth socket support`, reinstall with a system
> interpreter.

## Usage

```bash
melodyctl battery                 # Left 80%  Right 100%  Case 70%
melodyctl battery --json          # {"left":80,"right":100,"case":70}
melodyctl caps                    # supported command ids + features
melodyctl device                  # model, whitelist profile, verification status
melodyctl report                  # paste-safe compatibility report (read-only)
melodyctl gestures                # current gesture table
melodyctl gesture-set --list      # every valid ear/button/action/function value

# assign:  gesture-set <ear> <button> <action> <function>
melodyctl gesture-set left  tap  single play/pause
melodyctl gesture-set right tap  triple game        # game mode on triple-tap
melodyctl gesture-set both  tap  long   vol+        # both ears, hold = volume up
melodyctl game on
melodyctl anc                     # noise-cancelling state (anc set off/nc/deep/... on ANC models)
melodyctl watch                   # tap the buds to see live gesture events
```

`gesture-set` accepts numbers or names, validates the combination against the
device's advertised support, and refuses silently-invalid writes unless you
pass `--force`. All write commands (`game`, `gesture-set`, `eq-set`,
`anc set`) first read the device's product id and require `--force` on models
this project has not verified.

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

## Battery daemon (optional)

Publishes battery JSON for status bars/widgets:

```bash
mkdir -p ~/.config/systemd/user
cp daemon/melodyctl-daemon.service ~/.config/systemd/user/
systemctl --user enable --now melodyctl-daemon.service
cat "$XDG_RUNTIME_DIR/melodyctl-battery.json"
```

## Desktop widget

A DankMaterialShell (Quickshell) widget lives in the **`dms-plugins`** repo
(`melodyctl/` folder) and drives this CLI. It finds the `melodyctl` command on
`PATH`, or you can point it at a script path in its settings.

## Files

```
melodyctl/              the CLI package (protocol, transport, cli; stdlib only)
melodyctl.py            thin shim so `python3 melodyctl.py ...` keeps working
daemon/                 optional battery daemon + systemd unit
tools/                  helper scripts (probes, whitelist decrypt, profile build)
docs/protocol/          wire format, command ids, gesture codes (per-command docs)
whitelist.json          decrypted HeyMelody device whitelist (device configs)
```

The APK itself is **not** committed (~20 MB, vendor blob). Put
`heymelody-base.apk` in `apk/` and regenerate the whitelist with:

```bash
python3 tools/decrypt-whitelist.py apk/heymelody-base.apk whitelist.json
```

## How it works

The buds speak **OPOv1** over Bluetooth Classic RFCOMM (SPP). Frames are
`AA | LEN | 00 00 | cmd_lo cmd_hi | seq | plen_lo plen_hi | payload` (little
endian, response `cmd | 0x8000`). Battery is command `0x0106`; gestures are
`0x0108` (read) / `0x0401` (write); game mode is the feature switch `0x0403`
with feature id `6`. See [docs/protocol/](docs/protocol/index.md) for the
per-command reference.

## Limitations

- Hardware-verified on **ETI81 only**; the other 84 whitelist models are
  profile-based and `[untested]` (reads open, writes gated).
- Channel discovery is probe-based (12 → 15 → 1..30) because the Python
  stdlib has no SDP; `--channel` / `MELODYCTL_CHANNEL` override it.
- **No EQ on ETI81 and no ANC on ETI81** - neither is a feature of this model.
  `anc` exists for ANC models but has not been tested on ANC hardware.
- Firmware flashing is intentionally out of scope.

## License

[MIT](LICENSE). Not affiliated with or endorsed by OPPO / HeyTap. "OPPO",
"Enco" and "HeyMelody" are trademarks of their respective owners.
