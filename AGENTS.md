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
- One RFCOMM connection at a time — serialise all device access.
- DMS plugin version is pinned by the owner (1.3.0) — do not bump it there; CLI
  versions live in `pyproject.toml`.
- Keep CLI back-compat except for documented bug fixes (first one: `eq` → `fw`, v1.2.2).

## Layout

| path | what |
|---|---|
| `melodyctl.py` | CLI (Phase 4: `melodyctl/` package + thin shim) |
| `whitelist.json` | decrypted HeyMelody device whitelist (`compatWhiteList`, 85 devices) |
| `docs/` | protocol, devices, research, findings — the truth |
| `tools/` | probes (`rfcomm_scan`, `opo_probe`, …), decrypt + generators |
| `daemon/` | optional battery daemon for bars |

## On-hardware recipes

- Address: `--addr` or `MELODYCTL_ADDR` (default `6C:0D:E1:5F:DB:4D`). Buds drop to
  `Host is down` when idle; retry wakes them. `busy` = another connection is open
  (only one allowed at a time).
- Quick loop: `melodyctl caps`, `melodyctl devinfo`, `melodyctl fw`, `melodyctl battery --json`.
- New capture: raw request/response frames under `docs/protocol/captures/` with a
  header (date, product id, firmware, command, hex), referenced from `claims-matrix.md`.

## Current plan

`/home/chirag/.opencode/plan/melodyctl-family-expansion.md` (phases 0-6).
