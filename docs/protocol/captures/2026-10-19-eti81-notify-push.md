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
- The **case entry is always present** in both events while a bud moves in and
  out, so the app's "case level disappears when the buds are out" is UI
  behaviour, not the device dropping the entry.
- Battery is also re-pushed whenever it changes or the state changes; a single
  unchanged frame repeats often (safe to dedupe on the app side).
- Not observed here: the event-2 **in-ear** bit (bit 1) and any `0x8202`
  register-with-value frame. Both remain `[apk]`-derived.

Related: `docs/protocol/commands/notifications.md`, claims #7 / #33-#36.
