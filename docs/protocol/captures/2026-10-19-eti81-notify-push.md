# Capture — ETI81 notification pushes (2026-10-19)

Device: OPPO Enco Buds (ETI81) · product id `062410` · firmware 165/165/118
Tool: `melodyctl watch`, one RFCOMM session per run (channel 12).

Session setup (all we sent): `0x0200` → `0x8200` `[00][04][01 02 F1 F2]`
(4 advertised event ids), then one `0x0201` register per id. Everything below
arrived **unsolicited** on `0x0204` — no polling, no `0x0106`.

Payloads are as decoded by `parse_frames` (frame header stripped).

## Run 1 — case lid + bud placement

`0x0204` payloads in arrival order:

| payload (hex) | event | decoded |
|---|---|---|
| `01 03 01 32 02 50 03 64` | 1 battery | left 50% · right 80% · case 100% |
| `02 03 01 01 02 00 03 04` | 2 status | left out-of-case · right in-case · lid open |
| `01 03 01 32 02 50 03 64` | 1 battery | unchanged |
| `02 03 01 00 02 00 03 04` | 2 status | left back in case · lid open |
| `01 03 01 32 02 50 03 64` | 1 battery | unchanged |
| `01 03 01 32 02 50 03 64` | 1 battery | unchanged |
| `02 03 01 00 02 00 03 04` | 2 status | both in case · lid open |
| `01 03 01 32 02 50 03 64` | 1 battery | unchanged |
| `02 03 01 00 02 00 03 00` | 2 status | both in case · lid **closed** |
| `02 03 01 00 02 00 03 00` | 2 status | repeat of the same state |
| `01 03 01 32 02 50 03 64` | 1 battery | unchanged |

## Run 2 — take out / put back / close

| payload (hex) | event | decoded |
|---|---|---|
| `02 03 01 00 02 01 03 04` | 2 status | **right out-of-case** · left in-case · lid open |
| `01 03 01 5A 02 64 03 5A` | 1 battery | left 90% · right 100% · case 90% |
| `02 03 01 00 02 00 03 04` | 2 status | both in case · lid open |
| `01 03 01 5A 02 64 03 5A` | 1 battery | unchanged |
| `02 03 02 00 01 00 03 04` | 2 status | both in case · lid open — **right listed first** |
| `01 03 01 5A 02 64 03 5A` | 1 battery | unchanged |
| `02 03 02 00 01 00 03 00` | 2 status | both in-case · lid **closed** |
| `02 03 02 00 01 00 03 00` | 2 status | repeat |
| `01 03 01 5A 02 64 03 5A` | 1 battery | unchanged |

## Run 3 — replay through the new decoder (`--json`)

Same session shape (`0x0200`, then `0x0201` for ids `1` and `2` only). Arrival
order as emitted by `melodyctl watch -e 1,2 --json`:

| # | event | decoded by `decode_notify_event` |
|---|---|---|
| 1 | `2` | right out-of-case · left in-case · lid open |
| 2 | `1` | left 90% · right 100% · case 90% |
| 3 | `2` | both in case · lid open |
| 4 | `1` | unchanged |
| 5 | `2` | both in case · lid **closed** |
| 6 | `2` | repeat |
| 7 | `1` | unchanged |

This is the round-trip check for `protocol.decode_battery_event` /
`decode_status_event`: the raw bytes above and in runs 1-2 produce exactly
these values, and restricting registration to `-e 1,2` still receives both
events [hw:ETI81 2026-10-19].

## Run 4 — placement churn, link loss, reconnect (14:24–14:33)

`melodyctl watch --reconnect --json -e 1,2,242`, one process, three sessions
(the watchdog sat through two link losses and re-registered each time). The
watcher waited ~1 min for the buds before the first connect.

Session A — connected 14:24:57, closed by the device 14:27:39:

| +t | time | event | payload |
|---|---|---|---|
| 0.0 | 14:24:57 | 1 | `01 03 01 50 02 64 03 46` left 80 · right 100 · case 70 |
| 0.0 | 14:24:57 | 2 | `02 03 02 00 01 00 03 04` both in case · lid open |
| 0.0 | 14:24:57 | 1 | `01 03 01 50 02 64 03 46` repeat |
| 31.4 | 14:25:28 | 2 | `02 03 02 01 01 00 03 04` right out of case |
| 31.4 | 14:25:28 | 1 | `01 03 01 50 02 64 03 46` |
| 32.3 | 14:25:29 | 2 | `02 02 02 01 01 01` **both out — 2 entries, no case** |
| 32.3 | 14:25:29 | 1 | `01 02 01 50 02 64` **2 components, no case** |
| 80.3 | 14:26:17 | 2 | `02 03 02 00 01 01 03 04` right back in case |
| 80.3 | 14:26:17 | 1 | `01 03 01 50 02 64 03 46` case entry is back |
| 81.3 | 14:26:18 | 2 | `02 03 01 01 02 00 03 04` left out, **left listed first** |
| 91.1 | 14:26:28 | 2 | `02 02 01 01 02 01` both out |
| 103.4 | 14:26:40 | 2,1,2,1,2,1 | six frames in one batch: right out → both in, each change with its battery |
| 159.1 | 14:27:36 | 2,2,1 | `02 03 02 00 01 00 03 00` lid **closed** (×2) + battery |

`14:27:39` — device closed the socket (`Connection reset by peer`), 3 s after
the lid-closed frames. `14:27:46` reconnect attempt: `Host is down` (the device
sleeps with the lid shut). Then `reconnected - watching again.`

Session B — reopened lid, same process, no re-run:

| +t | time | event | payload |
|---|---|---|---|
| 178.1 | 14:27:55 | 1,2,1 | `01 03 01 50 02 64 03 46` / `02 03 02 00 01 00 03 04` lid open · both in case |
| 362.6 | 14:31:00 | 2,1,2,1 | right out → both out (`02 02 02 01 01 01` + `01 02 01 50 02 64`) |
| 455.4 | 14:32:32 | 2,1,2,1 | right in → both in |
| 464.6 | 14:32:42 | 2,2,1 | lid **closed** |

`14:32:44` — closed again (2 s later); `14:32:51` `Host is down`;
`reconnected - watching again.` (third session, killed while we started run 5).

Silent stretches inside those sessions — no frame arrived without a state
change: 48 s (both buds out), 56 s, **185 s** (both in, lid open), 92 s (both
out). Prior art polls every 60 s as a heartbeat backstop
[prior:buildscript@303997d]; nothing here did.

## Run 5 — same sequence with the frame source recorded (14:33–14:45)

`watch --reconnect --json`; every frame carried `"via": "0x0204"`.

| +t | time | event | payload |
|---|---|---|---|
| 0.0 | 14:33:34 | 2,1 | `02 03 02 01 01 00 03 04` right out · then `02 02 02 01 01 01` + `01 02 01 50 02 64` both out |
| 67.3 | 14:34:41 | 2,1,2,1 | right in (`02 03 02 00 01 01 03 04`) → both in (`02 03 02 00 01 00 03 04`) |
| 76.8 | 14:34:51 | 2,2,1 | `02 03 02 00 01 00 03 00` lid **closed** (×2) + battery |

`14:34:53` — closed (`Connection reset by peer`); `14:35:00` `Host is down`;
reconnected. The session then stayed open, with **no error**, until the window
expired (~10 min) and **pushed nothing**: reconnecting does not re-send state,
and there is no periodic frame. All 36 frames of run 4 and all 11 of run 5
arrived on `0x0204` — no `0x8202` register-with-value frame was ever seen, even
across four re-registrations.

## Run 6 — forced bulk register on a device that does not advertise it

`register_notify([1, 2], bulk=True)` against ETI81 (caps `ff 63`, group 22 not
set):

```
told-to-bulk: False | advertises: [1, 2, 241, 242]
register result: {"style": "per-event", "acks": {"1": 0, "2": 0}, "bulk_attempted": true}
```

`0x0205` was **silently ignored** — no `0x8205`, and no error frame either, so
the reply cannot be used as the gate. The capability bitmap is the only
reliable signal, and the automatic fallback to `0x0201` is what actually
registers. Both ids acked `0`.

## Run 7 — game-mode push, event `5`

Both buds already had **triple tap → game mode** bound (`melodyctl gestures`),
so no write was needed. Session: `0x0200` → `0x8200` `[00][04][01 02 F1 F2]`,
then one `0x0201` per id for `1 2 241 5` (`watch -e 1,2,241,5 -f`; ETI81 does
not advertise `5`, so `-f` was needed to send the request at all).

Registration answers, probed directly with hand-built `0x0201` frames
(`melodyctl raw "aa 08 00 00 01 02 00 01 00 <id>"`):

| request | reply | status |
|---|---|---|
| `0x0201` `[05]` | `8201` `[01][05]` | **refused** |
| `0x0201` `[02]` | `8201` `[00][02]` | accepted |
| `0x0201` `[03]` | `8201` `[01][03]` | refused |

`0x8201` payload = `[status][eventId]`; the firmware refuses ids it does not
advertise (`3`, `5`) with status `01`.

Pushes, in arrival order — twelve triple taps, each producing a gesture event
and then a game-mode event ~0.9 s later:

| payload (hex) | event | decoded |
|---|---|---|
| `F1 01 01 03 11 02 DE 00 00 00` | 241 | left · tap · triple → f17 game mode |
| `05 01 05 01` | 5 | state `01` |
| `F1 01 01 03 11 02 CA 00 00 00` | 241 | left · triple → game mode |
| `05 01 05 00` | 5 | state `00` |
| … (ten more, identical shape) | | `01`/`00` alternating with the taps |
| `F1 02 01 02 06 02 43 00` | 241 | right · **double** tap → f6 next song |
| `F1 02 01 02 06 02 C3 00` | 241 | right · double tap → next song (no event 5) |

Every game-mode frame is `05 01 05 <state>`: the state is the **last body
byte** (`payload[3]` / body[2]), one byte further in than the app's default
read — the per-product branch of claims #40, whose id list includes ETI81
(`062410`). The two leading bytes (`01`, `05`) were constant across all 20
frames in runs 7-8; only the last byte moved, and it tracked the game-mode
toggle (`01` = on, `00` = off). Non-game gestures produced **no** event 5.

## Run 8 — event `5` without registering it

Same tap sequence, but the session registered **only** the advertised ids
(`watch -e 1,2,241`: `registered 3 event(s) via per-event`, no `0x0201` for
`5`, no `-f`). Event 5 still arrived, same `05 01 05 <state>` frames, same
~0.9 s lag: 8 game-mode pushes across 8 triple taps.

So the game-mode push is **unsolicited**: ETI81 refuses to register event `5`
yet pushes it anyway. Registration is not what enables it, and the advertised
set (`1 2 F1 F2`) is not the full set of ids that can arrive.

## Corrections to runs 1-3

Runs 1-3 concluded "the case entry stays present in both events while buds move
in and out; the app's 'case level disappears' is UI logic". That was
over-generalised from frames where **one** bud was out. Runs 4 and 5 show the
device dropping the case entry itself once **both** buds leave the case:

- status count falls to 2 with no `03` row (`02 02 02 01 01 01`),
- battery count falls to 2 with no case level (`01 02 01 50 02 64`).

While at least one bud is in the case the case entry is present, carrying the
lid bit. So the app's UI rule and the wire agree; the decoder must not assume
three components (it already keys by component id and tolerates any count).

## What the capture fixes

- Both events are **pushes**; the app's `mNotificationCommandManager` path is
  the one in use, not `mPollCommandManager` [apk:HeadsetCoreService].
- Event 1 layout `[count][(component, level|charging<<7)...]` matches
  `BatteryInfo#<init>(int,byte[])` exactly; components 1/2/3 = L/R/case.
- Event 2 layout `[count][(component, flags)...]` matches
  `StatusInfo#<init>(int,byte[])`: bit 0 set = out of case, bit 1 = in ear,
  bit 2 set = lid open (the **case** entry carries the lid bit).
- **Entry order is not stable** (run 2 frame 5 lists right before left) → key
  by component id, never by position.
- The **case entry is dropped by the device** when both buds are out (runs 4-5);
  while a bud is in the case it is always present and carries the lid bit, so
  the app's "case level disappears when the buds are out" matches the wire.
- Battery is also re-pushed whenever it changes or the state changes; a single
  unchanged frame repeats often (safe to dedupe on the app side).
- **Push cadence is edge-triggered** (runs 4-5): no frame ever arrived without a
  bud, lid or battery change, across ~10 minutes of open, error-free session in
  run 5 and 48-185 s silent stretches in run 4. No heartbeat was observed, and
  reconnecting does not re-send state.
- **The link dies with the lid** (runs 4-5): the device closed the socket 2-3 s
  after the lid-closed frames, three times out of three, and was then
  unreachable (`Host is down`) until the lid was reopened. The old socket never
  revives, so a watcher must rebuild the session; re-registering then receives
  pushes again.
- Not observed here: the event-2 **in-ear** bit (bit 1), any `0x8202`
  register-with-value frame, and any set **charging** bit (the buds sat docked,
  at 80% and 100%, reporting `charging: false`). All remain `[apk]`-derived.
- Event `5` (game mode) **is** pushed — runs 7-8 — as `05 01 05 <state>`, even
  though the device refuses to register id `5` and does not advertise it.

Related: `docs/protocol/commands/notifications.md`, claims #7 / #33-#36,
#40 / #48-#49.
