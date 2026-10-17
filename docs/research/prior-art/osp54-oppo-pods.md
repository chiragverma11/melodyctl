# osp54/oppo-pods — prior art notes

Pinned commit `3dbdc475b3fcdb003c6e052eb4c8ee74345ea700`. Licence: MIT (verified via GitHub API 2026-10-17).

## What it is

- Noctalia bar plugin (Luau) plus a Python CLI, `scripts/oppo_ctl.py` (511 lines), which does all Bluetooth I/O (`plugin.toml:10` declares `license = "MIT"`; `plugin.toml:23-49` declares widget/panel/service entries).
- A bar widget, a floating panel, and a background service that polls the CLI every 4 s (`service.luau:111-112`).
- CLI requires `python3` and BlueZ with RFCOMM (`README.md:14-16`); no daemon of its own — each poll forks `python3` and opens a short-lived RFCOMM connection.

## Transport & protocol facts

- RFCOMM to the earbuds; channels tried are 12 then 13 (`scripts/oppo_ctl.py:130-141`), comment claims the HeyMelody SPP protocol is "exclusively on RFCOMM channel 12 (or 13 fallback on older models)" (`scripts/oppo_ctl.py:131`). Channel choice is remembered in a file, defaulting to 12 (`scripts/oppo_ctl.py:119-128`).
- Frame format: `AA <total_len> 00 00 <cmd lo> <cmd hi> <seq> <payload_len lo> <payload_len hi> <payload>` (`scripts/oppo_ctl.py:63-74`), with a resynchronising parser (`scripts/oppo_ctl.py:76-92`).
- Query sequence per status call: `0x0100` handshake, `0x0103` product ID, `0x0106` battery, `0x010C` ANC with payload `01 01` (`scripts/oppo_ctl.py:283-296`).
- Product ID reply `0x8103` decoded as bytes 1–3 reversed to hex (`scripts/oppo_ctl.py:313-315`). Battery reply `0x8106` (also sort-of active report `0x0204`) parsed as count-prefixed id/value pairs; id 1 = left, 2 = right, 3 = case; bit 7 of the value = charging, low 7 bits = level (`scripts/oppo_ctl.py:319-350`).
- ANC reply `0x810C` (also `0x0204`) is scanned for a `01 01` marker; claimed mode bytes: `0x02/0x10/0x20/0x40/0x80` = ANC, `0x04` (or `0x00` with next byte `0x01`) = transparency, `0x01/0x08` = off (`scripts/oppo_ctl.py:352-367`).
- ANC set command is `0x0404` with fixed seq `0xF0` and payload `01 01 01` off / `01 01 02` ANC / `01 01 04` transparency (`scripts/oppo_ctl.py:398-414`).
- Case battery of 0 with no charging flag is treated as "case offline" (buds in ears); last known level is preserved (`scripts/oppo_ctl.py:336-350`).
- On RFCOMM connect failure, the last cached state is returned if it said connected (`scripts/oppo_ctl.py:252-257`).
- Ships a hard-coded HeyMelody HMAC secret (`scripts/oppo_ctl.py:29`) and downloads official product renders from `iot-earbuds-*.allawnos.com` using signed requests (`scripts/oppo_ctl.py:143-222`).

## Device coverage & UX approach

- README claims the plugin "supports over 200 models" (`README.md:56`), but the shipped map has 20 entries (`scripts/oppo_ctl.py:40-61`) and is self-described as a "sample of most popular" (`scripts/oppo_ctl.py:39`). The source of the >200 figure is not contained in the repo.
- Device discovery: `bluetoothctl devices Connected` name matched against `("oppo", "enco", "oneplus", "buds", "realme", "dizo")` (`scripts/oppo_ctl.py:97-106`), with a UUID-based fallback (`scripts/oppo_ctl.py:107-114`) that is broken: `UUID_OPPO_SPP` is referenced at line 113 but never defined, so the `NameError` is swallowed by `except Exception: pass` (`scripts/oppo_ctl.py:115-116`).
- MAC can be forced per call via `--mac` or `OPPO_MAC`, otherwise auto-detected (`scripts/oppo_ctl.py:481-486`); the Noctalia setting `device_mac` is forwarded as `--mac` (`service.luau:10-17`, `README.md:35`).
- ANC cycling: `CYCLE_MODES = [ANC, TRANSPARENCY, OFF]` (`scripts/oppo_ctl.py:33-37`), right-click on the bar icon (`README.md:22-23`, `plugin.toml:29`). Cycle base is the cached `noise_mode`; unknown value jumps to ANC (`scripts/oppo_ctl.py:433-447`), and success fires a `notify-send` toast (`scripts/oppo_ctl.py:452-461`).
- Bar widget shows the lower bud's percentage as text, mode-dependent glyph otherwise (`widget.luau:40-69`); tooltip lists device, mode, L/R and case with charging state (`widget.luau:71-100`).
- Panel shows a downloaded device render (or bundled Enco Air4 Pro fallback image) and three battery columns (`panel.luau:106-142`), plus ANC/Transparency/Off buttons (`panel.luau:146-192`).
- CLI subcommands: `status`, `cached`, `set-anc <value>`, `cycle-anc` (`scripts/oppo_ctl.py:475`). Status output is a JSON object on stdout; a copy is also written to `$XDG_RUNTIME_DIR/oppo_pods_state.json` (`scripts/oppo_ctl.py:24-25`, `375-379`).
- Plugin IPC is not a socket: panel writes `{action, value, nonce}` into the Noctalia state key `oppo_pods_command` (`panel.luau:11-18`), the service watches it (`service.luau:108`) and executes, then re-polls. Status is shared via the state key `oppo_pods_snapshot` (`service.luau:5-6`, `widget.luau:103-108`).
- External IPC via Noctalia message bus: `set-noise` / `cycle-noise` (`README.md:38-52`, `service.luau:80-106`).

## Worth adopting

- Watch-and-cache split: the CLI prints full JSON state while the Luau side treats it as an opaque snapshot — a clean template for melodyctl's own state document.
- Framing helpers are minimal and self-contained (`scripts/oppo_ctl.py:63-92`); good cross-check against other implementations of the `AA …` frame.
- The `case_offline` concept (case reads 0 while buds are in ears; preserve last good level) with explicit UI labelling (`scripts/oppo_ctl.py:341-350`, `widget.luau:87-95`, `panel.luau:40-43`) is a UX pattern worth copying.
- Command verbs `status` / `cached` / `set-anc` / `cycle-anc` are a sound shape for a CLI, and "cycle from cached mode with ANC as the safe fallback" (`scripts/oppo_ctl.py:443-447`) avoids needing a read-back before write.
- i18n via translation catalogs for the plugin (`translations/en.json`, `ru.json`, `uk.json`) while the CLI keeps hard-coded Russian strings (e.g. `scripts/oppo_ctl.py:361,404`) — a split worth *not* copying.

## Contradictions / cautions

- Model count claim vs shipped list: >200 claimed (`README.md:56`) vs 20 entries (`scripts/oppo_ctl.py:40-61`); treat the >200 as unsubstantiated by this repo.
- Product ID conflict with buildscript-dev: this repo maps `045010` to "OnePlus Buds 3" (`scripts/oppo_ctl.py:54`); buildscript-dev maps `063C14` to "OnePlus Buds 3" (`daemon/oneplus-experience.py:65-74` repo B). Both decode the `0x8103` payload the same way, so this is a direct ID conflict between projects; neither was hardware-verified here.
- Channel claim conflicts with repo B: "exclusively … 12 (or 13 fallback)" (`scripts/oppo_ctl.py:131`) vs repo B's "control channel on Buds 3 is 15" (`daemon/oneplus-experience.py:26-27`).
- The UUID fallback in discovery appears dead code due to the undefined `UUID_OPPO_SPP` (`scripts/oppo_ctl.py:113-116`); name-keyword matching is the only working path, so oddly named clones won't be found.
- No read-back verification after `0x0404` ANC writes — set commands update the local cache optimistically (`scripts/oppo_ctl.py:416-427`).
- Every 4 s poll spawns `python3` and an RFCOMM connect (`service.luau:112`); heavier than repo B's persistent link, and battery state may flap on busy sockets since stale cache is served silently (`scripts/oppo_ctl.py:252-257`).
- The hard-coded HMAC signing secret (`scripts/oppo_ctl.py:29`) and CDN calls are an unusual dependency surface; treat as a protocol claim derived from the official app, not verified here.

## Licence & reuse

- MIT: `LICENSE` ("MIT License, Copyright (c) 2026 osp54"), `plugin.toml:10`, and the GitHub API check on 2026-10-17.
- Short quotes and protocol constants are reusable with attribution. The embedded HeyMelody HMAC secret string (`scripts/oppo_ctl.py:29`) originates from a third-party closed-source app and is not obviously covered by this repo's MIT grant — prefer documenting it as a claim rather than copying it into melodyctl.

## Sources

- https://github.com/osp54/oppo-pods at `3dbdc475b3fcdb003c6e052eb4c8ee74345ea700` (shallow clone, read-only, 2026-10-17).
- Read in full: `README.md`, `plugin.toml`, `scripts/oppo_ctl.py`, `service.luau`, `widget.luau`, `panel.luau`.
- Licence corroborated by local `LICENSE` and `plugin.toml` in addition to the stated GitHub API check.
