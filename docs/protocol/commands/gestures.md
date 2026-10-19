# Gestures — read `0x0108`, write `0x0401`

## Read (`0x0108` → `0x8108`)

- Response payload: `[status][count]`, then `count` entries
  `(deviceType, button, action, function)` [hw:ETI81 2026-10-17].
- ETI81 observed: L double = previous, R double = next, both triple = game
  mode, L long = volume down, R long = volume up [hw:ETI81 2026-10-17].

## Write (`0x0401` → `0x8401`)

- Payload: `[count, (deviceType, button, action, function) * count]`; our CLI
  writes one entry per request [hw:ETI81 2026-10-17].
- Ack payload `0` = ok, `1` = rejected (invalid slot/function)
  [hw:ETI81 2026-10-17].

## Field semantics

### `deviceType` (ear)

| value | meaning |
|---|---|
| 1 | left bud |
| 2 | right bud |
| 4 | both buds (write only; our CLI splits `4` into per-ear writes because some combined writes are rejected [hw:ETI81 2026-10-17]) |
| 255 | unspecified in the app [apk:N9/k] |

### `button` [apk:Ha.a#g]

| value | meaning |
|---|---|
| 1 | tap/touch area (the only kind on ETI81) |
| 2 / 3 | neckband volume +/- keys |
| 5 | middle button (used by OnePlus Bullets Wireless Z3 `051014` [wl:051014]) |
| 6 | both volume keys (long press) |

### `action` [apk:Ha.a#g]

| value | meaning |
|---|---|
| 1 | single tap |
| 2 | double tap |
| 3 | triple tap |
| 4 | long press |
| 5 | slide |
| 6 | super-long press |
| 7 / 8 | slide up / slide down |
| 16 / 17 / 18 | single / double / triple pinch |
| 20 | long pinch |
| 11 / 25 / 27 | alternate ids the app also renders (11 and 27 long press, 25 middle-button long press) |

The app has a second numbering for some device generations too: 27-34 mirror
1-8/16-18 (27 long press, 28-31 single/double/triple/super-long, 32-34 pinch),
35 super-long pinch, 36 middle-button call control, 37 middle-button long
press; 26 has no label in the current APK [apk:Ha.a#g]. Whitelist slots use
1-8, 11-18, 20, 25-27; a few legacy rows (actions 12-15) carry no `support`
mask and are disabled [wl].

### Function presets and wire codes

Each whitelist gesture slot carries a `support` bitmask over the app's
function presets; the app shows the set bits as the pickable functions
[apk:Ha.a#c]. The preset order below is the app's picker order
[apk:Ha.a.\<clinit\>], and each preset converts to the wire `function` code
with `Ha.a#b` [apk:Ha.a#b]:

| bit | preset | wire code |
|---|---|---|
| 0x200 | none | 0 |
| 0x4 | play/pause | 1 |
| 0x2 | listening music | 2 |
| 0x1 | voice assistant | 3 |
| 0x400 | adjust volume | 7 |
| 0x80 | noise switch | 8 |
| 0x100 | play collection | 9 |
| 0x800 | switch song | 10 |
| 0x8 | volume up | 11 |
| 0x10 | volume down | 12 |
| 0x1000 | switch device | 13 |
| 0x2000 | game mode | 17 |
| 0x10000 | zen mode | 18 |
| 0x8000 | collect music | 22 |
| 0x20000 | AI summary | 25 |
| 0x100000 / 0x200000 | AI translation / v2 | 26 |
| 0x40000 | reject call | 28 |
| 0x80000 | answer/hang up | 29 |
| 0x800000 | spy tap | 32 |
| 0x1000000 | GMN play/pause | 34 |
| 0x2000000 | GMN trigger | 35 |
| 0x20 | previous song | 5 (4 on the OnePlus branch) |
| 0x40 | next song | 6 (5 on the OnePlus branch) |
| 0x4000 | enter pairing | — (no wire code in `Ha.a#b`) |
| 0x400000 | clear pairing history | — (no wire code in `Ha.a#b`) |

Codes 4/5/6 are product-dependent: the app branch `d.I(product)` is true only
for the exact model names "OnePlus Buds" and "OnePlus Buds Z" [apk:d#I], so
on those two code 4 = previous song, 5 = next song and 6 is unused. The
presets carry *names*, so 0x20/0x40 are the only shifting bits.

### Per-device slots

Every device's whitelist `function.control` entries are its gesture slots:
`(action [, button])` plus a `support` mask (and optional label overrides
like `entryStrModify`). 83 of the 85 whitelist entries have a control table,
with slots using actions 1-8, 11-18, 20 and 25-27; only OnePlus Bullets
Wireless Z3 (`051014`) uses `button: 5` [wl]. The full tables ship in
`melodyctl/data/profiles.json` (`caps.gestures`), and `melodyctl gesture-set`
validates the requested combo against the connected device's slots before
writing (`--force` bypasses the check).

### Machine-readable list (`gesture-set --list --json`)

`melodyctl gesture-set --list` prints the vocabulary as text; with `--json` it
prints one object instead, and with `--product <id>` it adds that whitelist
profile's slots. This is the interface a front-end uses to render a per-model
editor — it is **offline** (no RFCOMM link, no device needed), so a widget that
already ran `melodyctl device --json` can look the table up by product id
without competing for the single connection.

```json
{
  "product_id": "062410", "device": "OPPO Enco Buds", "brand": "oppo",
  "verified": true, "oneplus_branch": false,
  "vocabulary": {
    "ears":      [{"id": 1, "name": "left"}, ...],
    "buttons":   [{"id": 1, "name": "tap/touch"}, ...],
    "actions":   [{"id": 1, "name": "single tap"}, ...],
    "functions": [{"id": 17, "name": "game mode"}, ...]
  },
  "slots": [
    {"button": 1, "action": 3, "ear": 2, "functions": [
      {"bit": 512, "name": "none", "function": 0},
      {"bit": 1, "name": "voice assistant", "function": 3},
      {"bit": 8192, "name": "game mode", "function": 17}
    ]}
  ]
}
```

- `slots` is keyed by `(button, action)` and mirrors what the write path
  accepts: a slot with no `support` mask (e.g. ETI81 action 12) is omitted, and
  `function: null` marks a preset the app offers but that has no wire code
  (`enter pairing`, `clear pairing history`), so it can never be written.
- `ear` is the whitelist's own ear field (informational — writes still carry the
  ear the user picked).
- `functions` in `vocabulary` and the codes inside `slots` already account for
  the OnePlus branch (`oneplus_branch: true`), so `previous song` is code 5
  there and code 4 on the branch models.
- Without `--product` the object still carries the vocabulary, with
  `product_id: null` and `slots: []`. An id that is not in the whitelist is a
  usage error (`probe: {"error": {"code": "unknown_device", ...}}` under
  `--json`).

### Allowed combinations on ETI81

From the whitelist `control` support masks [wl:062410]:

| action | support mask | allowed functions (wire codes) |
|---|---|---|
| 1 single tap | 516 (`512\|4`) | none(0), play/pause(1) |
| 2 double tap | 612 (`512\|4\|32\|64`) | none(0), play/pause(1), previous(5), next(6) |
| 3 triple tap | 8705 (`8192\|512\|1`) | none(0), voice assistant(3), game mode(17) |
| 4 long press | 536 (`512\|16\|8`) | none(0), volume up(11), volume down(12) |

Pinch models (X2/X3/X4, Buds Pro 2-4, …) advertise actions 16-18/20 with
their own masks; e.g. OPPO Enco X4 (`06EC10`) adds action 5 (slide,
`0xE00` = none|adjust-volume|switch-song) and a mask-less action 20 row.
The CLI derives everything from these tables instead of hardcoding.
