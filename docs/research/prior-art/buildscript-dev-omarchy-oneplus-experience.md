# buildscript-dev/omarchy-oneplus-experience — prior art notes

Pinned commit `303997dff7a1605dcaa0df17a57ff92ffd15ab4b`. Licence: MIT (verified via GitHub API 2026-10-17).

## What it is

- Omarchy bar plugin: a Python daemon (`daemon/oneplus-experience.py`, 628 lines), a Quickshell/QML panel (`Panel.qml`, 596 lines), a JS state model (`Model.js`), a `Service.qml` bridge, an install script (`setup`), and a systemd user unit (`daemon/oneplus-experience.service`). Manifest declares `license: MIT` and a bar widget (`manifest.json:7`, `manifest.json:14-16`).
- Daemon holds one persistent RFCOMM link to the earbuds, publishes state to `$XDG_STATE_HOME/oneplus-experience/status.json`, and accepts commands on `$XDG_RUNTIME_DIR/oneplus-experience.sock` (`daemon/oneplus-experience.py:2-11`, `29-31`); "Standard library only" (`daemon/oneplus-experience.py:6`).
- Two modes of use: daemon (`... daemon`), one-shot client (`... ctl VERB`, also plain `... VERB`), and `... status` to print the published file (`daemon/oneplus-experience.py:602-624`).
- `setup` writes a `oneplus-experience-ctl` wrapper into `~/.local/bin`, copies the unit into `~/.config/systemd/user`, and enables/restarts it — no root, no network (`setup:6-16`, `README.md:66-67`). The unit is `PartOf=graphical-session.target`, has `Restart=on-failure`, and a `ConditionPathExists=` pointing at the plugin location (`daemon/oneplus-experience.service:3-9`).
- Local copy note: the untracked `/home/chirag/stuff/melodyctl/oneplus-experience.py` (729 lines) is semantically identical to the pinned `daemon/oneplus-experience.py` (628 lines) — an `ast.dump` comparison of both parses is byte-identical, so the differences are reformatting/whitespace only (verified 2026-10-17). It matches repo B's daemon at this commit.
- Resource-usage claims (authors' measurements, not reproduced here): 8.9 MiB `MemoryCurrent`, 0.2% of one core idle, 0 PyPI packages, 124 KB on disk, measured on OnePlus Buds 3 / Omarchy 4 / Python 3.14 over a 30 s idle window with buds disconnected (`README.md:39-47`).

## Transport & protocol facts

- RFCOMM channels tried in order 15, 12, 13 (`daemon/oneplus-experience.py:26-27`); a working channel is remembered in `config.json` and tried first (`daemon/oneplus-experience.py:271-292`). Device must advertise SPP UUID `0000079a-d102-11e1-9b23-00025b00a5a5` (`daemon/oneplus-experience.py:25`, checked at `140-141`).
- Same `AA` frame format as repo A: `aa <len> 00 00 <cmd lo> <cmd hi> <seq> <plen lo> <plen hi> <payload>` (`daemon/oneplus-experience.py:38-39`, `78-80`), with a streaming reader (`daemon/oneplus-experience.py:83-106`). Outgoing seq wraps at `0xEF` (`daemon/oneplus-experience.py:268`).
- Static `HELLO` frame `AA 07 00 00 00 01 23 00 00 12` sent before the product query, then waits for `0x8103` (`daemon/oneplus-experience.py:42`, `279-281`).
- Opcode claims: `0x0103` product, `0x0105` version, `0x0106` battery, `0x010C` ANC, `0x010D` features, `0x010F` EQ; setters `0x0403` feature, `0x0404` ANC, `0x0406` EQ; `0x0200` broadcast codes, `0x0205` subscribe, `0x0204` notify (`daemon/oneplus-experience.py:43-46`).
- Product ID reply `0x8103` decoded as payload bytes 1–3 reversed to hex (`daemon/oneplus-experience.py:359-360`); firmware parsed from a CSV-looking `0x8105` reply (`daemon/oneplus-experience.py:361-367`); EQ from `0x810F`/`0x0504` (`daemon/oneplus-experience.py:379-382`).
- Battery reply `0x8106`: count-prefixed pairs, id 1/2/3 = left/right/case, level = `raw & 0x7F`, charging = `raw & 0x80` (`daemon/oneplus-experience.py:338-356`). A complete reply that omits a bud marks it unavailable (i.e. in the closed case) (`daemon/oneplus-experience.py:351-355`); case reading 0 with no charging keeps the last value (`daemon/oneplus-experience.py:347-349`).
- After the broadcast-codes exchange (`0x8200` → subscribe `0x0205`), pushes arrive as `0x0204` (`daemon/oneplus-experience.py:383-393`); a push whose shape isn't a known battery layout schedules an exact re-read 0.3 s later (`daemon/oneplus-experience.py:390-391`).
- Noise-control bitmap claims: read-back bit → mode `{0:off, 3:off, 1:anc, 2:transparency, 8:transparency, 4/5/6:anc, 7:smart}` and `{4:max, 5:moderate, 6:mild}`; write bits `off=0, transparency=2, smart=7`, levels `max=4, moderate=5, mild=6` (`daemon/oneplus-experience.py:56-62`). The comment notes "The Buds read back a different bit than they are written with for Off and Transparency" (`daemon/oneplus-experience.py:56-57`).
- ANC write = `0x0404` payload `01 01` + little-endian bitmask, `width = bit // 8 + 1` (`daemon/oneplus-experience.py:474-477`); generic (no levels) ANC falls back to bit 1 (`daemon/oneplus-experience.py:441-444`).
- Feature switch ids: wear `0x04`, game `0x06`, spatial `0x1B` (`daemon/oneplus-experience.py:50-54`); feature query payload `0B 05 04 0B 11 13 18 06 1B 1C 27 28` (`daemon/oneplus-experience.py:47`), setter `0x0403` (`daemon/oneplus-experience.py:465-468`).
- Command verbs over the socket: `connect`, `disconnect`, `refresh`, `noise:<mode>`, `level:<strength>`, `eq:<n>`, `feature:<name>:<on|off>` (`daemon/oneplus-experience.py:412-470`); `anc_level` is persisted in config and reused (`daemon/oneplus-experience.py:441-442`, `448-452`).
- `connect`/`disconnect` shell out to `bluetoothctl` and reset the poll timer (`daemon/oneplus-experience.py:415-427`).
- Status file is deduped (write only when JSON text changes) and written atomically via tmp+`os.replace` (`daemon/oneplus-experience.py:213-221`); the socket is `chmod 0600` (`daemon/oneplus-experience.py:507`) and both socket and status file are removed on shutdown (`daemon/oneplus-experience.py:548-554`).

## Device coverage & UX approach

- Verified: only "OnePlus Buds 3", "verified on hardware (firmware 127.127.101)" (`README.md:53`). Everything else: "Battery and basic noise control, untested" (`README.md:54`); `MODELS` contains exactly one product ID, `063C14`, with modes/levels/EQ/features (`daemon/oneplus-experience.py:65-74`); unknown IDs fall back to `GENERIC_MODEL` with `anc/transparency/off`, no levels/EQ/features (`daemon/oneplus-experience.py:75`). README invites adding product IDs to `MODELS` (`README.md:56-57`).
- UX: right-click the bar icon cycles modes (`Panel.qml:109-112`, `Service.qml:98-103`); left-click opens a control center with battery rows for L/R/case (`Panel.qml:228-242`), mode rows (`Panel.qml:254-267`), a strength segmented control shown only when ANC is active and levels exist (`Panel.qml:28`, `284-298`), EQ grid (`Panel.qml:302-328`), and feature toggles (`Panel.qml:334-350`). Keyboard: `n` ANC, `s` smart, `t` transparency, `o` off, `1`–`9` EQ, `j/k`+Enter cursor movement, `r` refresh (`Panel.qml:125-147`; key list also `README.md:23-24`).
- Bar shows the lower bud's level and turns urgent at ≤ 20% (`Service.qml:24-29`, `Model.js:5`, `Panel.qml:31`, `101-104`).
- Notifications: connect announcement with L/R/case and mode (`daemon/oneplus-experience.py:247-261`); low-battery at thresholds 20/10/5, critical at ≤ 10 (`daemon/oneplus-experience.py:36`, `229-245`); optional `libnotify` (`README.md:69-71`).
- CLI examples documented: `oneplus-experience-ctl status|noise:anc|level:mild|eq:0|feature:game:off` (`README.md:83-89`).
- QML reads state via `FileView` with `watchChanges: true` on `status.json` (`Service.qml:33-34`, `163-171`); `Model.parseStatus` validates a required `schema_version` and refuses newer schemas (`Model.js:3`, `60-73`). Commands run as a `Process` invoking `oneplus-experience-ctl` (`Service.qml:76-80`, `173-188`); the panel reads `pods.status` through the `Service` component (`Panel.qml:26-31`, `81-84`).
- Optimistic UI: panel holds the requested mode/level/EQ for up to 4 s until the daemon confirms it in `status.json` (`Service.qml:37`, `47-68`, `82-90`, `142-146`); command errors surface as elided stderr text (`Service.qml:137-140`, `Model.js:113-116`).
- IpcHandler exposes `open/close/toggle/refresh/noise/connection/status` (`Panel.qml:86-95`).

## Worth adopting

- Architecture: one long-lived process owning the RFCOMM link + a Unix socket for commands + an atomically-written, deduped JSON status file is a clean separation that works for any bar/CLI consumer; the `schema_version` gate in the reader (`Model.js:66-73`) is a good forward-compatibility pattern for melodyctl's own status document.
- Send-safe read/write bit split for noise control, including the documented read-vs-write divergence for off/transparency (`daemon/oneplus-experience.py:56-62`) — a concrete cross-check target for melodyctl's own opcode tables.
- Deliberate "re-read instead of guessing" handling of unknown push shapes (`daemon/oneplus-experience.py:390-391`) and "re-read defensively on set replies" (`daemon/oneplus-experience.py:392-393`).
- Optimistic pending-merge in the UI with a settle timeout (`Service.qml:47-68`, `142-146`) — avoids UI lag without lying about hardware state.
- Case-closed detection semantics: bud missing from a complete battery reply = unavailable (`daemon/oneplus-experience.py:351-355`), case 0 = keep last reading (`daemon/oneplus-experience.py:347-349`).
- Persisting the working RFCOMM channel in config after first success (`daemon/oneplus-experience.py:290-292`) reduces connect latency on odd models.
- Security posture for an IPC surface: socket `0600`, tmp+rename writes, cleanup on exit (`daemon/oneplus-experience.py:507`, `216-220`, `548-554`).

## Contradictions / cautions

- README says "Live, not polled. The buds push changes" (`README.md:21-22`), but the daemon also polls the device every 4 s (`daemon/oneplus-experience.py:34`, `517-519`) and re-queries battery every 60 s (`daemon/oneplus-experience.py:35`, `523-525`). The push path is real (`0x0204` notify handling) but polling is the backstop; marketing and code diverge in emphasis, not in fact.
- Product ID conflict with osp54/oppo-pods: this repo maps `063C14` to OnePlus Buds 3 (`daemon/oneplus-experience.py:65-74`); repo A maps `045010` to OnePlus Buds 3 (`osp54/oppo-pods scripts/oppo_ctl.py:54`). Both reverse bytes 1–3 of the `0x8103` payload, so the disagreement is about the ID values, not the decoding. Recorded as conflicting claims.
- RFCOMM channel conflict: "control channel on Buds 3 is 15; older OPPO parts use 12 or 13" (`daemon/oneplus-experience.py:26-27`) vs repo A's "exclusively … 12 (or 13 fallback)" (`osp54/oppo-pods scripts/oppo_ctl.py:130-131`). The probe order 15/12/13 in this repo at least tolerates both claims.
- Noise-mode bit semantics are asserted from reverse engineering ("as HeyMelody numbers them", `daemon/oneplus-experience.py:49`) and the read/write asymmetry is explicitly documented as a claim (`daemon/oneplus-experience.py:56-57`). Not independently verified here.
- Opcode claim relevant to melodyctl's 0x0105-vs-EQ confusion, recorded *as a claim*: this project treats `0x0105` as a version/firmware query (`daemon/oneplus-experience.py:43`, parsed at `361-367`) and EQ as query `0x010F` / set `0x0406` (`daemon/oneplus-experience.py:44-46`, `379-382`, `461`). Do not treat as truth; cross-check on hardware.
- Generic (untested) devices get only `anc/transparency/off` and a bit-1 ANC write (`daemon/oneplus-experience.py:75`, `441-444`); everything else in `supports` is empty, so the UI degrades gracefully rather than misreporting (`Panel.qml:28`, `244-350` visibility guards).
- Resource numbers are the authors' single-machine measurements (`README.md:41-47`); plausible for a stdlib-only Python loop using `select`, but not reproduced for these notes.
- Protocol provenance is cross-project: credits list OppoPodsWindows (GPL-3.0), oppo-pods, and oneplus-buds-omarchy, with an explicit "only protocol facts were used … never their code" statement (`README.md:102-114`).

## Licence & reuse

- MIT: `LICENSE` ("MIT License, Copyright (c) 2026 GM"), `manifest.json:7`, and the GitHub API check on 2026-10-17.
- Reusable with attribution. The provenance note (`README.md:109-114`) is worth preserving: derived works should keep the distinction between MIT code here and protocol facts attributed to the GPL-3.0 OppoPodsWindows lineage.
- The local untracked copy in melodyctl (`/home/chirag/stuff/melodyctl/oneplus-experience.py`) is semantically identical to this commit's daemon (AST comparison), so it can be treated as an MIT vendored copy — record provenance if it stays in-tree.

## Sources

- https://github.com/buildscript-dev/omarchy-oneplus-experience at `303997dff7a1605dcaa0df17a57ff92ffd15ab4b` (shallow clone, read-only, 2026-10-17).
- Read in full: `README.md`, `daemon/oneplus-experience.py`, `daemon/oneplus-experience.service`, `Model.js`, `Service.qml`, `Panel.qml`, `setup`, `manifest.json`.
- Local file `/home/chirag/stuff/melodyctl/oneplus-experience.py` compared against the pinned daemon via `diff` and `ast.dump` (2026-10-17): 729 vs 628 lines, whitespace/formatting only, semantically identical.
- Licence corroborated by local `LICENSE`/`manifest.json` in addition to the stated GitHub API check.
