# Notifications — `0x0200` / `0x0201` / `0x0204` (and `0x8202` / `0x0205`)

## Advertise (`0x0200` → `0x8200`)

- No payload; response `[status][count][eventId...]`
  [hw:ETI81 2026-10-17].
- ETI81 advertises `[1, 2, 241, 242]` [hw:ETI81 2026-10-17]: `1` = battery,
  `2` = bud status, `241` (`0xF1`) = user interaction, `242` (`0xF2`) =
  connected-device list.
- Same shape in prior art, different id sets: Buds Pro `01 02 03 04 06 08 0a`,
  Buds Pro 2 ten codes including `f1 f2 f3` [prior:gazz@abe70f4]
  [prior:leaf@feb7b70].

## Register (`0x0201` → `0x8201`)

- Payload `[eventId]`; works on ETI81 [hw:ETI81 2026-10-17] — our CLI
  registers each advertised id and reads the per-event status byte
  (payload[0]).
- The app has both flows: `0x0201` for one id, and `0x0205`
  (`[count][eventId...]` → `0x8205`) for all of them [apk:j#c]. It picks
  `0x0205` only when the device advertises `0x0205` as supported, otherwise it
  falls back to `0x0201` per id [apk:n6.b#c] — so per-event registration is the
  family-wide-safe path (OQ-2 resolved).
- Register only ids the device advertised: `notify_caps()` is the allow-list.

## Pushes (`0x0204`)

- `payload[0]` = event id, `payload[1:]` = event body [hw:ETI81 2026-10-19].
- The app routes the whole `0x0204` family through one parser and switches on
  that byte [apk:j#b]; the ids below are its names.

| id | name | body |
|---|---|---|
| `1` | battery | `[count][(component, level\|charging<<7) * count]` |
| `2` | bud status | `[count][(component, flags) * count]` |
| `3` | noise mode | sub-tagged like `0x010c` replies |
| `4` | compactness (fit) | two detections |
| `5` | game mode | one status byte |
| `6` | multi-connect | device list |
| `8` | hearing-detect status | *(detection)* |
| `10` | zen mode | one status byte |
| `11` | personalized noise result | *(result)* |
| `13` | triangle info | *(capsule)* |
| `14` | ear-scan result | *(result)* |
| `15` | public event | bitmask + one value |
| `16` | oneshot | oneshot state |
| `17` | tone change | tone list |
| `0xF1` (241) | user interaction | `[deviceType, button, action, function, scene]` |
| `0xF2` (242) | connected devices | device list |
| `0xF4` | diagnosis json | JSON text |
| `0xF5`/`0xF6` | head-motion type / try result | one byte |
| `0xF7` | voice-assist control | config |
| `0xF8` | LE/BR switch state | *(state)* |
| `0xF9` | AI-translation audio focus | one byte |

- Everything except `1`/`2`/`0xF1` is named from the app's switch but **not
  yet decoded** [apk:j#b]; unknown bodies are kept as raw hex.
- Prior art reads the multiplex as type `0x01` battery, `0x03` ANC change,
  `0x04` fit detection, `0x06` connected-device list
  [prior:leaf@feb7b70] — consistent with ids 1/3/4/6 above; battery is the
  only one both sides decode, and it agrees.
- Prior-art discipline worth keeping: subscribe only to advertised codes and
  never treat unknown/unsolicited payloads as state proof
  [prior:gazz@abe70f4].

### Battery event (`1`)

`[count][(component, level | charging<<7) * count]` — identical to the `0x0106`
reply body, just with the event id where `0x0106` has a status byte
[hw:ETI81 2026-10-19] [apk:BatteryInfo#<init>]. Components `1`/`2`/`3` =
left/right/case. The app additionally rounds reports up to a per-device
`batteryRadix` before display [apk:BatteryInfo#fixBatteries] — that value is
not in our decrypted whitelist, so `melodyctl` shows the raw level.

### Bud-status event (`2`)

`[count][(component, flags) * count]` [hw:ETI81 2026-10-19]
[apk:StatusInfo#<init>]:

| bit | set means |
|---|---|
| `0x01` | bud is **out of the case** |
| `0x02` | bud is **in the ear** |
| `0x04` | case **lid is open** (case entry only) |
| `0x08` | safe-reminder active |

The app inverts bits 0 and 2 into positive accessors (`isInBox`,
`isBoxCoverClosed`) [apk:StatusInfo#<init>]. The case entry's other bits are
not meaningful.

Two decoding rules from hardware:

- **Component order is not stable** — the device listed right before left in
  one frame [hw:ETI81 2026-10-19]. Key by component id.
- The **case entry is always present** in both event kinds while buds move in
  and out; the app hiding the case level when the buds are out is UI logic,
  not the wire [hw:ETI81 2026-10-19].

### `0x8202` — register-with-value (device-initiated)

The app also handles `0x8202` as an asynchronous push whose body is
`[status][eventId][body]` — the same event, one byte later — and logs it as a
"registered notification" [apk:j#c]. It never sends `0x0202` itself, so there is
nothing for us to request; the response bit is set on the device's frame. Not
observed on ETI81 [hw:ETI81 2026-10-19]; `melodyctl watch` accepts one if a
device sends it (the app's route is the registered-value path used for the
initial value).

## Relation to polling

`0x0106` (battery) stays useful as an explicit one-shot read, but a subscribed
session gets the same data pushed, plus case/bud state that has no poll at all.
The app keeps both paths side by side (`mNotificationCommandManager` vs
`mPollCommandManager`) [apk:HeadsetCoreService].

Related: `melodyctl watch`, [opo-v1.md](../opo-v1.md),
[captures/2026-10-19-eti81-notify-push.md](../captures/2026-10-19-eti81-notify-push.md).
