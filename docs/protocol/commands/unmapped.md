# Unmapped / not-advertised commands

Commands that are unlocked on ETI81 but whose behaviour is **not yet
interpreted** (OQ-8), plus commands ETI81 does not advertise at all. None of
these were sent by us; do not invent payload layouts.

## Unlocked on ETI81 (caps bitmap), still not interpreted

| cmd | notes |
|---|---|
| `0x0107` | poll; no app-side name found (OQ-8) |
| `0x0109` | poll; the app sends it right after registering notification handlers — candidate "initial state" query, no reply classifier found (OQ-8) |
| `0x0402` | write; no app-side name found (OQ-8) |
| `0x0408` | write; no app-side name found (OQ-8) |
| `0x0409` | write; no app-side name found (OQ-8) |
| `0x0416` | write; unlocked together with the gesture pair (caps group 3); not yet interpreted (OQ-8) |

Unlocked status is from the ETI81 bitmap decode [hw:ETI81 2026-10-17] (group
table in [handshake.md](handshake.md)); the poll/write grouping follows the
`0x01xx` query / `0x04xx` control convention [prior:leaf@feb7b70]. None of the
six has an ack classifier in the app
[apk:SetCommandStateInfo#isSuccess] (see below).

## Named by the app's write-ack classifier

The app tags write acknowledgements by response id (`request + 0x8000`) with
named predicates, `SetCommandStateInfo#is*Rsp` [apk:SetCommandStateInfo]. Two
ETI81-unlocked writes had no name until this pass:

| cmd | app-side name | tag |
|---|---|---|
| `0x0400` | find mode ("find earbuds") | `[apk:SetCommandStateInfo#isFindModeRsp]`; matches prior art's placement [prior:leaf@feb7b70] [untested] |
| `0x0405` | compactness detection (fit detection) | `[apk:SetCommandStateInfo#isCompactnessDetectRsp]`; the SDK keeps `DeviceInfo#getCompactnessDetectionInfo()` [apk:DeviceInfo#getCompactnessDetectionInfo] |

Payload layouts are not documented — do not send these yet.

### Response name table (family-wide)

Same classifier; most requests below are **not** unlocked on ETI81. Response =
request id + `0x8000`.

| response | request | name (app) |
|---|---|---|
| `0x8400` | `0x0400` | find mode |
| `0x8401` | `0x0401` | key function |
| `0x8403` | `0x0403` | switch feature |
| `0x8404` | `0x0404` | noise reduction |
| `0x8405` | `0x0405` | compactness detection |
| `0x8406` | `0x0406` | EQ status |
| `0x840d` | `0x040d` | hearing-enhancement detection |
| `0x840e` | `0x040e` | process hearing-enhancement detection |
| `0x8411` | `0x0411` | ear restore info |
| `0x8412` | `0x0412` | personal noise |
| `0x8414` | `0x0414` | free dialog |
| `0x8418` | `0x0418` | EQ info (custom bands) |
| `0x841c` | `0x041c` | account key |
| `0x841d` | `0x041d` | screen-off broadcast delay time |
| `0x8421` | `0x0421` | spine range detection |
| `0x842c` | `0x042c` | oneshot record start/stop |
| `0x8f00` | `0x0f00` | switch debug |

Each row is a method on `com.oplus.melody.btsdk.api.data.SetCommandStateInfo`
(its `is…Rsp` predicate); ack status byte `0` = ok
[apk:SetCommandStateInfo#isSuccess].

## Not advertised on ETI81

- `0x010d` batch status — no ETI81 support [hw:ETI81 2026-10-17]. Prior art:
  the request is a count + feature ids; replies are `(featureId, bool)` pairs
  or a structured status/count list [prior:leaf@feb7b70] [untested]. The
  original Buds Pro never answered it (even after registration); Buds Pro 2
  returned six pairs — `0x04` wear detection, `0x06` low latency, `0x0b`
  hearing enhancement, `0x11` multipoint, `0x18` high-quality audio, `0x05`
  unnamed [prior:gazz@abe70f4]. Model-gated; do not generalise.
- `0x0423` game *sound* — not advertised on ETI81 [hw:ETI81 2026-10-17];
  prior art lists a game-sound enable command [prior:leaf@feb7b70] [untested].
- `0x0406` EQ select — not advertised on ETI81, which has no EQ at all
  [wl:062410]. Prior art: payload is the preset `protocolIndex`
  [prior:leaf@feb7b70] [prior:gazz@abe70f4] [untested]; `melodyctl eq-set`
  stays experimental and other-models-only [hw:ETI81 2026-10-17].
- `0x0f00` switch debug — app-side name from the ack classifier
  [apk:SetCommandStateInfo#isSwitchDebugRsp] [apk:SetCommandStateInfo]; ETI81
  does not advertise its caps group (23) [hw:ETI81 2026-10-17]. Payload
  unknown; do not send.

Related: [opo-v1.md](../opo-v1.md) (master table),
[commands/feature-switch.md](feature-switch.md) (why `0x010d` matters for
read-back).
