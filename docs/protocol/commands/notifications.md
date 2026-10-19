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

## Register (`0x0201` / `0x0205`)

- `0x0201` payload `[eventId]` → `0x8201` `[status][eventId]`; `0x0205` payload
  `[count][eventId...]` → `0x8205` [apk:j#c]. Both work on ETI81's firmware
  ([hw:ETI81 2026-10-19]).
- The app picks between them by *capability*, not by the advertised event set:
  it sends one `0x0205` when the device advertises that command, otherwise one
  `0x0201` per id [apk:j#c] (`n6.b#c` is the support test).
- ETI81's caps bitmap is `ff 63` — groups 0-9, 13, 14 — so `0x0205` (group 22,
  [handshake.md](handshake.md)) is **not** advertised and the app itself uses
  the per-event path there. `melodyctl watch` prefers `0x0205` when the caps
  bitmap advertises it, and falls back to `0x0201` per event if the bulk
  register is refused — so the path we can test on hardware is the one we use.
- The ack is **not** a usable gate: ETI81 ignores `0x0205` outright — no
  `0x8205`, and no error frame either [hw:ETI81 2026-10-19]. Only the bitmap
  tells you whether the device understands it.
- Register only ids the device advertised: `notify_caps()` is the allow-list
  [prior:gazz@abe70f4]. `melodyctl watch -f` overrides that for a **probe**
  only — an unadvertised id that never arrives proves nothing, and one that
  does arrive is a lead to capture, not state proof.
- A refusal is not proof the id never arrives: ETI81 answers status `01` to
  `0x0201` `[05]` and then pushes event `5` unsolicited anyway (run 8), so a
  watcher must decode an id it never registered. The **advertised set is not
  exhaustive** [hw:ETI81 2026-10-19].
- Right after registering, the app sends `0x0109` **only when the device
  advertises it** [apk:j#c] — a candidate "initial state" query (OQ-8); ETI81
  does not advertise it.

## Pushes (`0x0204`)

- `payload[0]` = event id, `payload[1:]` = event body [hw:ETI81 2026-10-19].
- The app routes the whole `0x0204` family through one parser and switches on
  that byte [apk:j#b]; the ids below are its names.
- **Edge-triggered, no heartbeat.** Nothing arrives between state changes; a
  bud, lid or battery change re-sends status + battery, often repeating the
  same frame. ETI81 held a session open for ~10 minutes, with no error, and
  pushed nothing [hw:ETI81 2026-10-19]. A poll is the only way to refresh on
  demand (`0x0106`), and prior art keeps a 60 s poll as a backstop
  [prior:buildscript@303997d].
- **Reconnecting re-sends nothing** — subscription is not a state request.
- **The link dies with the lid.** Going back in the case with the lid shut
  closes the RFCOMM socket 2-3 s after the lid-closed frames, and the device is
  then unreachable until the lid reopens; the old socket never revives
  [hw:ETI81 2026-10-19]. `melodyctl watch --reconnect` rebuilds the session and
  re-registers.

| id | name | body |
|---|---|---|
| `1` | battery | `[count][(component, level\|charging<<7) * count]` |
| `2` | bud status | `[count][(component, flags) * count]` |
| `3` | noise mode | sub-tagged like `0x010c` replies |
| `4` | compactness (fit) | two detections |
| `5` | game mode | one status byte (offset varies by product - see below) |
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
| `0xF2` (242) | connected devices | `[count][(mac6 reversed, connectTimes u16 LE, nameLen u8, name) * count]` |
| `0xF4` | diagnosis json | JSON text |
| `0xF5`/`0xF6` | head-motion type / try result | one byte |
| `0xF7` | voice-assist control | config |
| `0xF8` | LE/BR switch state | *(state)* |
| `0xF9` | AI-translation audio focus | one byte |

- Everything except `1`/`2`/`5`/`0xF1` is named from the app's switch but **not
  yet decoded** [apk:j#b]; unknown bodies are kept as raw hex.
- Prior art reads the multiplex as type `0x01` battery, `0x03` ANC change,
  `0x04` fit detection, `0x06` connected-device list
  [prior:leaf@feb7b70] — consistent with ids 1/3/4/6 above; battery is the
  only one both sides decode, and it agrees.
- Prior-art discipline worth keeping: subscribe only to advertised codes and
  never treat unknown/unsolicited payloads as state proof
  [prior:gazz@abe70f4].

### What varies per model

The parsers above have no product-id branch [apk:j#b], so the *layouts* are
family-wide. What differs is:

- **Which ids can arrive at all** — the `0x8200` advertised set, and nothing
  else is registered. Buds Pro advertised `01 02 03 04 06 08 0a`, Buds Pro 2
  ten codes `01 02 03 04 08 0b f1 f2 f3 0a` [prior:gazz@abe70f4].
- **How to register** (`0x0205` vs `0x0201`) — see above.
- **Event `5` (game mode)** reads its state byte at body offset `+2`
  (`payload[3]`) instead of `+1` (`payload[2]`) on product ids `062410`,
  `062810`, `063410`, `063010` — ETI81 among them [apk:j#b] [hw:ETI81
  2026-10-19]. `melodyctl watch` implements the branch and passes the product
  id down; the observed frame is `05 01 05 <state>`.
- **Event `2`'s in-ear bit** is only meaningful where the whitelist enables
  `function.wearDetection` — absent on 47 of the 85 entries, ETI81 included,
  which is why we have never seen it [wl:062410] [hw:ETI81 2026-10-19].
- **Three entries** (OPPO Enco Clip, Clip2, OnePlus Buds Clip) carry no
  `function.batteryInfo`, so event `1` may never fire there
  [wl:06E010] [wl:06B810] [wl:06E410].
- `0x0204` is not the only push channel: the app handles EQ and other
  notifications on other commands too (e.g. `0x0504`) [prior:leaf@feb7b70] —
  outside this doc.

### Battery event (`1`)

`[count][(component, level | charging<<7) * count]` — identical to the `0x0106`
reply body, just with the event id where `0x0106` has a status byte
[hw:ETI81 2026-10-19] [apk:BatteryInfo#<init>].

- **One frame carries every component** — a change in any bud or the case
  re-sends them all; charging is bit 7 of the same byte, so charge start/stop
  would ride this event too [hw:ETI81 2026-10-19] (no set bit seen yet - OQ-11).
- **The case entry disappears when both buds are out**: the device drops
  component `3` (and the count falls to 2) rather than sending a stale case
  level [hw:ETI81 2026-10-19]. While a bud is in the case the entry is present
  and carries the lid bit, so decoders must accept any count and key by
  component.
- Component ids: `1`/`2`/`3` read as left/right/case, but the app's vocabulary
  is the enum `BatteryType` {LEFT, RIGHT, BOX, **SINGLE**} [apk:BatteryType], so
  case-less or single-battery models are not guaranteed to use those ids. Every
  decoded entry therefore also carries its raw id as `component`, and unknown
  ids print as `idN` instead of a body part (OQ-12).
- The app rounds a level up to a multiple of the whitelist's `batteryRadix`
  (`fixBattery`; a radix ≤ 1 means no rounding) [apk:BatteryInfo#fixBatteries].
  The key is absent from the decrypted whitelist and the DTO defaults it to 0
  [apk:WhitelistConfigDTO.Function#<init>], so no rounding applies to these 85
  models — `melodyctl` shows the raw level.

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
- **The count is not fixed either**: when both buds are out of the case the
  device drops the case entry, in this event *and* in event `1`
  [hw:ETI81 2026-10-19]. Never assume three components.

### Game-mode event (`5`)

Observed on ETI81 (runs 7-8) as `05 01 05 <state>`: a constant leading `01`,
then `05` (the event id again — meaning unknown), then the state byte,
non-zero = on. The state is the **last body byte** there, one byte further in
than the app's default read, which is the per-product branch claims #40
describes — the four ids it lists (`062410`, `062810`, `063410`, `063010`)
include ETI81's own. The default (one byte earlier) is still `[apk]`-derived;
`melodyctl watch` gets the product id from `0x0103` at session start and picks
the offset.

Three things worth knowing before relying on it:

- **Unsolicited.** ETI81 *refuses* to register id `5` (`0x8201` → status `01`,
  like every unadvertised id) yet pushes it anyway — run 8 saw it in a session
  that never mentioned `5` and only registered `1 2 241`. Registration is not
  what enables it, and `0x8200` is not the full set of ids that can arrive.
- **Edge-triggered like the rest**, ~0.9 s after the gesture that caused it, and
  only for game-mode changes: the double taps in runs 7-8 produced no event `5`.
- It reports the *result*, so it is a genuine state source, not a copy of what
  the controlling host sent.

### `0x8202` — register-with-value (device-initiated)

The app also handles `0x8202` as an asynchronous push whose body is
`[status][eventId][body]` — the same event, one byte later — and logs it as a
"registered notification" [apk:j#c]. It never sends `0x0202` itself, so there is
nothing for us to request; the response bit is set on the device's frame. Not
observed on ETI81 — across four re-registrations every frame arrived on
`0x0204` [hw:ETI81 2026-10-19] → OQ-14; `melodyctl watch` accepts one if a
device sends it (the app's route is the registered-value path used for the
initial value).

## Relation to polling

`0x0106` (battery) stays useful as an explicit one-shot read, but a subscribed
session gets the same data pushed, plus case/bud state that has no poll at all.
The app keeps both paths side by side (`mNotificationCommandManager` vs
`mPollCommandManager`) [apk:HeadsetCoreService].

Related: `melodyctl watch`, [opo-v1.md](../opo-v1.md),
[captures/2026-10-19-eti81-notify-push.md](../captures/2026-10-19-eti81-notify-push.md).
