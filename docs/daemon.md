# `melodyctl daemon` — one owner of the RFCOMM link

The device allows **one** RFCOMM connection at a time (a second attempt gets
errno 16, `busy`), and its pushes are edge-triggered: the battery/state a held
session collects is the freshest data the device will ever hand out, and
reconnecting re-sends nothing [hw:ETI81 2026-10-19]. The app itself keeps a
long-lived notification session next to its polling manager
[apk:HeadsetCoreService].

The daemon is that session, exposed to everything else:

```
$XDG_RUNTIME_DIR/melodyctl/state.json    last known state, for file readers
$XDG_RUNTIME_DIR/melodyctl/daemon.sock   line-delimited JSON, for commands
$XDG_RUNTIME_DIR/melodyctl/daemon.lock   flock: one daemon per user
```

It is **opt-in** — nothing auto-starts it, and `melodyctl` behaves exactly as
before when it is not running.

## Running it

```bash
melodyctl daemon              # foreground; Ctrl-C stops it
melodyctl daemon --retry-max 30 --quiet
MELODYCTL_DEBUG=1 melodyctl daemon   # log client-request timings
```

As a systemd user unit (recommended for a widget):

```bash
mkdir -p ~/.config/systemd/user
cp daemon/melodyctl-daemon.service ~/.config/systemd/user/
# edit ExecStart if `command -v melodyctl` is not ~/.local/bin/melodyctl,
# and set Environment=MELODYCTL_ADDR=... if your buds are not the default
systemctl --user daemon-reload
systemctl --user enable --now melodyctl-daemon
journalctl --user -u melodyctl-daemon -f
```

While it runs, its session is the daemon's: the session thread connects,
identifies the product (`0x0103`), registers the advertised push ids, seeds the
battery with one `0x0106` read, and then holds the link. On any link loss it
comes back with exponential back-off (2 s doubling to `--retry-max`, default
60 s) — and a client that asks for something while it is waiting makes it try
again immediately, so a returning pair of buds is picked up in seconds rather
than minutes.

## `state.json`

Written atomically (`tmp` + rename) whenever a push changes it, and rewritten
at least every 60 s so `ts` stays meaningful.

```json
{
  "version": "1.5.0", "addr": "6C:0D:E1:5F:DB:4D",
  "session": "connected",
  "product": "062410", "device": "OPPO Enco Buds", "channel": 12,
  "registered": [1, 2, 241, 242],
  "battery": {"left": {"component": 1, "level": 50, "charging": false}, "right": {...}},
  "status": {"left": {"component": 1, "in_case": false, "in_ear": false,
                      "cover_open": true, "safe_remind": false}, "case": {...}},
  "game": {"on": true, "state": 1},
  "updated": 1792407289.7, "ts": 1792407340.1, "error": null
}
```

Rules a reader can rely on:

- `session` is `connected` or `waiting`. **Gate on it**: while `waiting`, the
  `battery`/`status`/`game` values are the last ones seen, not current ones.
  (`error` then carries the classified reason, e.g. `unreachable`/`busy`.)
- `updated` is when the device last told us something; `ts` is when the file
  was last written. A file with an old `ts` means the daemon is gone (crash, or
  `systemctl --user stop`), so treat it as no daemon at all.
- `battery`/`status` are **replaced** per event, never merged: the device drops
  the case entry from both events once both buds are out [hw:ETI81
  2026-10-19], and a stale case level must disappear with it.
- `battery`, `status` and `game` are `null` until the device says something.
  `battery` is seeded with one `0x0106` poll on connect; **`status` and `game`
  are push-only** — there is no query for either — so they stay `null` after a
  reconnect until the next event. `status` follows a case/bud change; `game`
  follows a game-mode change (event `5`, which ETI81 pushes unsolicited even
  though it refuses to register it — claims #48/#49).

## `daemon.sock`

Unix socket, one JSON object per line, request then reply. Same error shape as
the CLI: `{"ok": false, "error": {"code": ..., "message": ..., "hint": ...}}`.

| request | reply |
|---|---|
| `{"op": "ping"}` | daemon identity + session: `version`, `pid`, `addr`, `channel`, `product`, `device`, `session`, `registered`, `error` |
| `{"op": "state"}` | `{"ok": true, "state": {...}}` — the `state.json` object |
| `{"op": "send", "cmd": N, "payload": "<hex>", "wait": 2.5}` | `{"ok": true, "frames": [{"cmd": N, "payload": "<hex>"}]}` |
| `{"op": "raw", "packet": "<hex>", "wait": 2.5}` | `{"ok": true, "reply": "<hex>"}` |
| `{"op": "subscribe"}` | the hello object, then a stream of `{"event": {...}}` and `{"session": "..."}` lines |

`send` is the only thing that needs the device; the frame-level API is enough
because every high-level call in the CLI (`battery`, `caps`, `gestures`,
`set_gesture`, ...) is expressed in terms of it. A push that lands inside a
`send` reply window is fanned out like any other — it is not swallowed by that
window.

`subscribe` carries exactly what `melodyctl watch` prints: decoded event
objects (`event_id`, `event`, decoded sub-object, `hex`, `via`, `ts`) plus
session transitions, so an attached `watch` shows drops and recoveries the
daemon rides out.

## What the CLI does

Every command that talks to the device goes through the daemon when one is
running, and opens its own RFCOMM session when it is not. The distinction that
matters:

- **socket failure** (no socket, dead socket, unreadable reply) → fall back to
  a direct session, silently.
- **an error reply** (the daemon is waiting, the device refused, ...) → report
  it. The daemon owns the link; opening a second one would only fight it.

`--no-daemon` forces a direct session (useful for `report`, `raw`, or when
diagnosing the daemon itself). Two things genuinely need the direct link:

- `watch -f` (register ids the device does not advertise). With a daemon
  running, `watch` attaches instead, `-e` becomes a filter on the daemon's
  stream, and `--reconnect`/`--retry-max` are the daemon's business.
- `watch -e` still works attached, but only for ids the daemon registered
  (i.e. the advertised set).

## Implementation note

The session thread is the only one that touches the device, so it must come up
for air between reads: it uses `Buds.read_events` (a plain call that returns
after at most one drain window) rather than the `iter_events` generator. A
generator only returns from `next()` once it has decoded an event, and pushes
are edge-triggered — driving the session through it starves queued client
requests until the device happens to send something (measured: 94 s on
hardware).

## Limits

- Event `5` (game mode) is push-only and unsolicited: the daemon cannot ask for
  the current value, so `game` is `null` until something changes it.
- The daemon holds the RFCOMM link, so a *different* app (the phone's HeyMelody)
  and the daemon contend for it exactly as two CLI processes do today. `busy`
  shows up as `session: waiting` with `error.code == "busy"`.
