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

## Field semantics (`N9/k`, `N.b`, `Ha.a.b`)

| field | values |
|---|---|
| `deviceType` | `1` left, `2` right, `4` both (write only — our CLI splits `4` into per-ear writes because some combined writes are rejected [hw:ETI81 2026-10-17]); `255` = unspecified in the app [apk:N9/k] |
| `button` | `1` tap/touch — the only kind on ETI81; `6` slide/pinch group, which `N9/k` maps actions 28-37 onto [apk:N9/k] |
| `action` | `1` single, `2` double, `3` triple, `4` long press; `16-19` single/double/triple/long pinch (button 6) [apk:N9/k] |

Codes 4/5/6 are product-dependent: the app branch `d.I(product)` is true only
for "OnePlus Buds" / "OnePlus Buds Z", so ETI81 takes the OPPO column
[apk:d#I] [apk:N.b] [apk:Ha.a.b].

| code | OPPO (ETI81) | OnePlus branch |
|---|---|---|
| 0 | none | none |
| 1 | play/pause | play/pause |
| 3 | voice assistant | voice assistant |
| 4 | *(unused)* | previous song |
| 5 | previous song | next song |
| 6 | next song | *(unused)* |
| 11 | volume up | volume up |
| 12 | volume down | volume down |
| 17 | game mode | game mode |

Other codes exist in the app (2 resume, 7 adjust volume, 8 noise reduction,
9 play collection, 10 switch song, 13 switch device, 18 zen mode, 22 collect
music, 25-35 AI/GMN/call features) but are **not advertised for ETI81**
[wl:062410] [apk:N.b].

## Allowed combinations on ETI81

From the whitelist `control` support masks [wl:062410]:

| action | mask | allowed functions |
|---|---|---|
| 1 single tap | 516 (`512\|4`) | none, play/pause |
| 2 double tap | 612 (`512\|4\|32\|64`) | none, play/pause, previous(5), next(6) |
| 3 triple tap | 8705 (`8192\|512\|1`) | none, voice assistant(3), game mode(17) |
| 4 long press | 536 (`512\|16\|8`) | none, volume up(11), volume down(12) |

Other combinations are rejected by the device; `melodyctl gesture-set` gates
on these masks (`--force` bypasses the gate only).
