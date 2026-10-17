# OPOv1 / HeyMelody protocol notes

Reverse engineered from HeyMelody (`com.heytap.headset`, `com.oplus.melody.btsdk`)
and verified against an **OPPO Enco Buds (ETI81)**, whitelist id `062410`.

## Transport

- **Bluetooth Classic RFCOMM (SPP)**. The app discovers the service via SDP
  using one of two UUIDs:
  - `0000079A-D102-11E1-9B23-00025B00A5A5` (most devices, incl. ETI81)
  - `00001107-D102-11E1-9B23-00025B00A5A5`
- The RFCOMM **channel is whatever SDP reports** (channel **12** on ETI81; this
  tool currently hardcodes 12).
- Only **one** RFCOMM connection at a time. Coexists with A2DP.

## Framing

```
AA | LEN | 00 00 | cmd_lo | cmd_hi | seq | plen_lo | plen_hi | payload...
```

| Field | Notes |
|---|---|
| `AA` | magic |
| `LEN` | `7 + len(payload)` (single byte for small frames) |
| `00 00` | constant |
| `cmd` | 16-bit **little endian** (`cmd = cmd_hi << 8 | cmd_lo`) |
| `seq` | sequence byte |
| `plen` | payload length, 16-bit little endian |
| `payload` | command-specific |

Response `cmd = request_cmd | 0x8000` (e.g. `0x0106` -> `0x8106`). Reads and
writes work with only the capability "hello" frame; there is **no auth token**.

## Command ids

| cmd | dir | meaning |
|---|---|---|
| `0x0100` | poll | capability bitmap (`getRemoteCapability`, also used as hello) |
| `0x0103` | poll | device info |
| `0x0105` | poll | component versions: `status, count`, then ASCII triples `(component,kind,value)`; kind 2 = firmware |
| `0x0106` | poll | battery |
| `0x0108` | poll | touch gestures (key function) read |
| `0x0200` | write | subscribe to notifications (no payload) |
| `0x0201` | write | register one event id: `[eventId]` |
| `0x0204` | push | device event; `payload[0]` = event id |
| `0x0401` | write | set gesture: `[count, (deviceType,button,action,function)*count]` |
| `0x0403` | write | feature switch: `[featureId, enable]` (feature 6 = game mode) |
| `0x0406` | write | EQ select by protocol index (**not advertised on ETI81**; no EQ) |
| `0x0423` | write | game *sound* (**unsupported on ETI81**) |

### Capability bitmap (`0x0100`)

A bitmap indexing `CAP_GROUPS` (`p026b8.a.f14745a`) to the command ids it
unlocks. ETI81 replies `00 FF 63`, unlocking:
`0x0105 0x0106 0x0107 0x0108 0x0109 0x010c 0x0400 0x0401 0x0402 0x0403 0x0404
0x0405 0x0408 0x0409 0x0416`.

## Battery (`0x0106`)

Reply payload: `[00][count][(device, charging<<7 | level) * count]`.

- `device`: `1` = left, `2` = right, `3` = case (from `C0922j.java`).
- `charging`: bit 7; `level`: bits 0-6.

## Versions (`0x0105`)

Reply payload: `[status][count]` then an ASCII CSV of `count` triples
`(component, kind, value)`. Components 1/2/3 = left/right/case; kind 2 is the
component firmware (kinds 1 and 4 not yet interpreted).

ETI81: left 165, right 165, case 118. The shape is cross-confirmed on other
models (Buds Pro 541/541/510, Buds Pro 2 196/196/101 - Gazz's phone-verified
captures), so `melodyctl fw` should generalise; left == right and the case
differs in every observed capture.

## Gestures

Read `0x0108`, write `0x0401`. Each entry is
`(deviceType, button, buttonAction, function)`.

- **deviceType** (ear): `1` = left, `2` = right, `4` = both (write only; the
  tool splits `4` into per-ear writes). `255` = unspecified in the app.
- **button**: `1` = tap/touch (the only one on ETI81), `6` = slide/pinch group
  (`N9/k.java` maps actions 28-37 to button 6).
- **buttonAction**: `1` single tap, `2` double, `3` triple, `4` long press;
  `16-19` are single/double/triple/long **pinch** (button 6).

### Function codes (`N.b`, `Ha.a.b`)

Codes **4 / 5 / 6 are product-dependent**. `d.I(product)` is true only for
`"OnePlus Buds"` / `"OnePlus Buds Z"`; ETI81 is neither, so the OPPO branch
applies:

| code | OPPO branch (ETI81) | OnePlus branch |
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
music, 25-35 AI/GMN/call features) but are **not advertised for ETI81**.

### Allowed combinations on ETI81

From the whitelist `control` support masks (`062410`):

| action | support mask | allowed functions |
|---|---|---|
| 1 single tap | 516 (`512\|4`) | none, play/pause |
| 2 double tap | 612 (`512\|4\|32\|64`) | none, play/pause, previous(5), next(6) |
| 3 triple tap | 8705 (`8192\|512\|1`) | none, voice assistant(3), game mode(17) |
| 4 long press | 536 (`512\|16\|8`) | none, volume up(11), volume down(12) |

`0x0401` ack payload: `0` = ok, `1` = rejected (invalid slot/function).

## Game mode

Feature switch `0x0403` with payload `[6, enable]`. Ack `00` on success. The
device does **not** push feature-6 state, so read-back is not available.

## Notifications

Subscribe `0x0200` -> capabilities `[1, 2, 241, 242]`; register each with
`0x0201 [eventId]`. Pushes arrive on `0x0204` with `payload[0]` = event id.
`0xF1` (241) = user interaction:
`[deviceType, button, action, function, scene]`.

## Whitelist

HeyMelody ships `res/raw/heymelody_app_whitelist.json` encrypted as
**AES-256-GCM + GZIP**, keyed by the **SHA-256 of the APK signing certificate
DER** (`RepackagingDetector.U.b`). Decrypt with
`tools/decrypt-whitelist.py`. It lists 85 devices (53 OPPO, 32 OnePlus) with
per-model feature maps; ETI81 = `062410`.
