# AGENTS.md — read this first

melodyctl is a Linux CLI + protocol toolkit for **HeyMelody-family** earbuds
(OPPO Enco / OnePlus Buds / realme). Device data comes from the decrypted
HeyMelody whitelist (`whitelist.json`); behaviour is **verified only on OPPO
Enco Buds (ETI81, product id `062410`)** unless a claim says otherwise.

## Truth machinery (non-negotiable)

- `docs/` is the source of truth — not chat history, not memory, not code comments.
- Every factual claim carries an evidence tag:

  | tag | meaning |
  |---|---|
  | `[hw:ETI81 YYYY-MM-DD]` | observed on real hardware (capture committed under `docs/protocol/captures/`) |
  | `[wl:<id>]` | from the HeyMelody whitelist entry `<id>` (what the app itself does) |
  | `[apk:<class#method>]` | decompiled app logic (cite paths only, never code bodies) |
  | `[prior:<project>@<sha>]` | from prior-art docs/code (facts with attribution; never copied code) |
  | `[untested]` | whitelist- or prior-art-derived, not verified by us |
  | `[assumption]` | only allowed in `open-questions.md`, never as a doc fact |

- `docs/research/claims-matrix.md` and `docs/research/open-questions.md` are
  updated **in the same commit** as any change that adds, refutes, or answers a fact.
- Device support ladder: `verified` (we ran it) > `external` (named third party's
  published evidence) > `untested`. Write commands are gated by profile; queries may run.

## Read order

1. `AGENTS.md` (this file)
2. `docs/research/claims-matrix.md`
3. `docs/research/open-questions.md`
4. `docs/protocol/index.md`
5. the doc for your task

## Rules

- Scope: devices in `whitelist.json` `compatWhiteList`. No claims about anything else.
- **Licence firewall**: GazzasaurusRex/oneplus-buds-omarchy, osp54/oppo-pods and
  buildscript-dev/omarchy-oneplus-experience are MIT (facts + attribution fine).
  Leaf-lsgtky/OppoPods has **no licence** — facts with citation only, never code.
- CLI is stdlib-only; install via `uv tool install` (see README). Keep it that way.
- Errors: short title + Details; single-line JSON under `--json`; never tracebacks.
- One RFCOMM connection at a time — serialise all device access. A running
  `melodyctl daemon` owns the link; every command routes through it and
  `--no-daemon` forces a direct session.
- DMS plugin version lives in `dms-plugins/melodyctl/plugin.json` and is bumped
  only when the owner asks for a plugin release; CLI versions live in
  `pyproject.toml` + `melodyctl/__init__.py`.
- Keep CLI back-compat except for documented bug fixes (first one: `eq` → `fw`, v1.2.2).

## Layout

| path | what |
|---|---|
| `melodyctl/` | CLI package: `protocol` (framing/decoders), `transport` (RFCOMM session), `errors`, `cli`, `data/` (generated profiles) |
| `melodyctl.py` | thin shim → `melodyctl.cli:main` (so `python3 melodyctl.py` still works) |
| `melodyctl/data/` | generated device profiles (whitelist → capabilities; regen via `tools/build-profiles.py`) |
| `whitelist.json` | decrypted HeyMelody device whitelist (`compatWhiteList`, 85 devices) |
| `docs/` | protocol, devices, research, findings — the truth |
| `tools/` | probes (`rfcomm_scan`, `opo_probe`, …), decrypt + generators |
| `tests/` | stdlib unittest: golden decoders (ETI81 captures), Phase 4 refactor regression |
| `daemon/` | systemd user unit for `melodyctl daemon` (holds the RFCOMM link, publishes `state.json`, serves commands - see `docs/daemon.md`) |

## On-hardware recipes

- Address: `--addr` or `MELODYCTL_ADDR` (default `6C:0D:E1:5F:DB:4D`). Buds drop to
  `Host is down` when idle; retry wakes them. `busy` = another connection is open
  (only one allowed at a time).
- Push captures: start with the buds **out of the case**. A cased pair with the lid
  shut is disconnected (so `watch` cannot even connect), and the device closes the
  RFCOMM link when it goes back to sleep — an open session then goes silent for good.
  `melodyctl watch --reconnect` waits for the buds at startup and rebuilds the
  session after each drop.
- Quick loop: `melodyctl caps`, `melodyctl device`, `melodyctl fw`, `melodyctl battery --json`.
- New device/coverage work: `melodyctl report` (safe to paste) is the fact-collection step for upgrading a row in `docs/devices/coverage.md`.
- New capture: raw request/response frames under `docs/protocol/captures/` with a
  header (date, product id, firmware, command, hex), referenced from `claims-matrix.md`.

## Maintainer recipes

- Whitelist regeneration: the HeyMelody APK is **not** committed (~20 MB vendor
  blob). Put `heymelody-base.apk` in `apk/` (gitignored), then:
  `python3 tools/decrypt-whitelist.py apk/heymelody-base.apk whitelist.json`,
  followed by `python3 tools/build-profiles.py` to regenerate
  `melodyctl/data/profiles.json` + `docs/devices/coverage.md`.

## Current plan

`/home/chirag/.opencode/plan/melodyctl-family-expansion.md` (phases 0-8: family
expansion, push channel — done) and
`/home/chirag/.opencode/plan/melodyctl-daemon-and-dms-widget.md` (the daemon owns
the RFCOMM link and the DMS widget reads push state — **released as CLI 1.5.0
(`v1.5.0`) + plugin 1.5.0 (`melodyctl-v1.5.0`)**; the plan file lists what is
still unverified: one daemon-side lid-close cycle, a human look at the widget
popout with the buds out, and a real second device for the non-ETI81 rows).

The follow-up — stale state after a reconnect, the daemon's own `updated`
timestamp, the idle `--poll` that doubles as a liveness check, and the widget's
game-mode/refresh/reconnect handling — is
`/home/chirag/.opencode/plan/melodyctl-daemon-widget-1.5.1-fixes.md`, released as
**CLI 1.5.1 (`v1.5.1`) + plugin 1.5.1 (`melodyctl-v1.5.1`)**.
