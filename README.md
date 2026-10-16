# melodyctl

Control **OPPO Enco Buds (ETI81)** from Linux over the same wire protocol
HeyMelody uses: read per-ear battery, read/write touch gestures, toggle game
mode, and watch for button events. No Android app, no BLE pairing dance -
just Bluetooth Classic RFCOMM.

> **Scope:** verified only on the **OPPO Enco Buds (ETI81 / whitelist id
> `062410`)**. The underlying protocol (OPOv1 over SPP) is shared with other
> OPPO / OnePlus earbuds, but nothing else is tested here - see
> [Limitations](#limitations).

## What you get

| Command | Does |
|---|---|
| `melodyctl battery` | Left / Right / Case levels (`--json`, `--json-full`) |
| `melodyctl monitor` | Poll battery continuously |
| `melodyctl caps` | Decode the device capability bitmap |
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

Only one RFCOMM connection is allowed at a time (it coexists fine with A2DP).

## Install

```bash
# install as a command (recommended) -> provides `melodyctl` on PATH
pipx install git+https://github.com/chiragverma11/melodyctl

# or from a local checkout
git clone https://github.com/chiragverma11/melodyctl
pipx install ./melodyctl

# or just run it in place
python3 melodyctl.py --help
```

## Usage

```bash
melodyctl battery                 # Left 80%  Right 100%  Case 70%
melodyctl battery --json          # {"left":80,"right":100,"case":70}
melodyctl caps                    # supported command ids + features
melodyctl gestures                # current gesture table
melodyctl gesture-set --list      # every valid ear/button/action/function value

# assign:  gesture-set <ear> <button> <action> <function>
melodyctl gesture-set left  tap  single play/pause
melodyctl gesture-set right tap  triple game        # game mode on triple-tap
melodyctl gesture-set both  tap  long   vol+        # both ears, hold = volume up
melodyctl game on
melodyctl watch                   # tap the buds to see live gesture events
```

`gesture-set` accepts numbers or names, validates the combination against the
device's advertised support, and refuses silently-invalid writes unless you
pass `--force`.

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
melodyctl.py            the CLI (single file, no third-party deps)
daemon/                 optional battery daemon + systemd unit
tools/                  reverse-engineering helpers (probes, whitelist decrypt)
docs/protocol.md        wire format, command ids, gesture codes
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
with feature id `6`. See [docs/protocol.md](docs/protocol.md) for the full
reference.

## Limitations

- Verified on **ETI81 only**. Other OPPO / OnePlus models share the protocol
  but differ in feature set; the RFCOMM channel is discovered by the app via
  SDP (two service UUIDs are in use), while this tool currently uses channel
  **12**.
- **No EQ control** (the device ignores EQ writes) and **no noise reduction**
  (not a feature on ETI81).
- Firmware flashing is intentionally out of scope.

## License

[MIT](LICENSE). Not affiliated with or endorsed by OPPO / HeyTap. "OPPO",
"Enco" and "HeyMelody" are trademarks of their respective owners.
