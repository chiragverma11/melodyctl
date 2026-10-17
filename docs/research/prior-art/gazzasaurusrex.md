# GazzasaurusRex/oneplus-buds-omarchy — prior art notes

Pinned commit `abe70f4b6e8f55cc8f6a4888c04ddead8a087e33` (default branch `main`). Licence: MIT (verified via GitHub API 2026-10-17).

Read-only clone at `/tmp/opencode/prior/gazz`. Marker legend: **[V]** their own hardware-verified claim (two reference devices only); **[U]** community/registry-derived, speculative, or explicitly unresolved evidence; **[M]** measurement method, tooling, or documentation/process state. Every factual bullet carries `[prior:gazz@abe70f4]` and cites `path:line` in their repo.

## What it is

- **[V]** [prior:gazz@abe70f4] Omarchy bar widget plus Python backend for OnePlus/OPPO earbuds; status "0.1.0 release candidate", no release tag, independent of OnePlus/OPPO — README.md:6-8.
- **[V]** [prior:gazz@abe70f4] Only two hardware-verified models: Buds Pro (`060C14`, fw 541.541.510, Light/Deep/Smart) and Buds Pro 2 (`062014`, fw 196.196.101, Light/Medium/Deep/Smart) — README.md:21-25.
- **[V]** [prior:gazz@abe70f4] Strict layering: bluez discovery → RFCOMM transport → 0xAA framing → product profiles → backend orchestration → session → CLI; QML owns presentation only — docs/backend-cli.md:7-14, README.md:189-193.
- **[V]** [prior:gazz@abe70f4] Runtime needs only system Python 3.11+, `dbus-python`, and BlueZ; no PyPI packages, daemon, root, or audio-stack changes — README.md:49-58.
- **[V]** [prior:gazz@abe70f4] One RFCOMM control channel is a hard constraint: the plugin must be disabled before running the CLI or other earbud tools — README.md:144-146, docs/measurements/connection-lifecycle.md:63-65.

## Transport & protocol facts

- **[V]** [prior:gazz@abe70f4] Original Buds Pro exposes SPP plus vendor service `00001107-d102-11e1-9b23-00025b00a5a5`; connect-only test to RFCOMM channel 15 succeeded — docs/protocols/OPOv1.md:7. Pro 2 uses `0000079a-...` on the same channel — OOv1.md:88; channel 15 is the transport default — src/oneplus_buds/transport.py:15.
- **[U]** [prior:gazz@abe70f4] Related devices may expose `0000079a-...` over RFCOMM or as BLE with `0100079a` write / `0200079a` notify characteristics; transport must stay separate from framing — OOv1.md:9, docs/research/open-source.md:16.
- **[V]** [prior:gazz@abe70f4] Frame: `AA total_length 00 00 cmd_lo cmd_hi seq payload_len_lo payload_len_hi payload`; little-endian; frame length is `total_length + 2`; no checksum — OOv1.md:13-17; src/oneplus_buds/protocol.py:93-113.
- **[V]** [prior:gazz@abe70f4] Outer length is authoritative: `0x8100` capability payload reported an inner length one byte shorter, an unsolicited `0x0204` three bytes larger; concatenated frames still split exactly — OOv1.md:39; protocol.py:124-130.
- **[V]** [prior:gazz@abe70f4] Product ID `0x0103` → `0x8103`: status plus 3-byte ID rendered as uppercase hex (e.g. `060C14`) — OOv1.md:26; protocol.py:163-168.
- **[V]** [prior:gazz@abe70f4] Version `0x0105` → `0x8105`: status, count, ASCII triples `(component, kind, value)`; kind-2 values joined left/right/case produce 541.541.510 and 196.196.101, both user-confirmed against the HeyMelody display; firmware is only formatted when both left and right kind-2 records exist — OOv1.md:45-55; protocol.py:192-202.
- **[V]** [prior:gazz@abe70f4] Battery `0x0106` → `0x8106`: pairs `[component, raw]`, 1/2/3 = left/right/case, `raw & 0x7f` = percent, bit 7 = charging; Buds Pro prefixes a count, parser accepts count-prefixed or pair-only — OOv1.md:37; protocol.py:205-222.
- **[V]** [prior:gazz@abe70f4] Notification negotiation: `0x0200` → `0x8200` (status, count, event IDs); `0x0205` subscribes. Buds Pro advertised `01 02 03 04 06 08 0a`; subscribing to that exact set echoed each code as a little status pair, then an immediate `0x0204` snapshot. Pro 2 advertised ten codes `01 02 03 04 08 0b f1 f2 f3 0a` with a different acknowledgement shape, so the backend does not assume one layout — OOv1.md:59-61; protocol.py:249-255; src/oneplus_buds/session.py:148-165.
- **[V]** [prior:gazz@abe70f4] `0x010d` batch status: no response on original Pro even after registration — OOv1.md:41, 59; Pro 2 returned six `(feature ID, boolean)` pairs: 0x04 wear detection, 0x06 low latency, 0x0b hearing enhancement, 0x11 multipoint, 0x18 high-quality audio, 0x05 unnamed; a returned ID establishes capability even when the value is false — OOv1.md:63; protocol.py:37-43.
- **[V]** [prior:gazz@abe70f4] Auth flow: HELLO `AA 07 00 00 00 01 23 00 00 12`, 2 s wait; REGISTER `AA 0C 00 00 00 85 41 05 00 00 B5 50 A0 69` (fixed four-byte token), 1.5 s wait — OOv1.md:69, 75-76; protocol.py:47-48; session.py:136-146.
- **[V]** [prior:gazz@abe70f4] ANC query `0x010c` → `0x810c` with request `01 01`; ANC set `0x0404` payload `01 01 <bitmap>` where the bit index comes from the product profile — OOv1.md:29-30; src/oneplus_buds/profiles.py:17-24.
- **[V]** [prior:gazz@abe70f4] Product `060C14` bitmap: Off=`01`, Transparency=`02`, light=`04`, deep=`08`, smart=`10`; an authenticated `04` write read back as light — OOv1.md:65-67.
- **[V]** [prior:gazz@abe70f4] Product `062014` bitmap spans two bytes; main writes Off=index 0, On=1, Transparency=2; levels Deep=4, Medium=5, Light=6, Smart=7; read aliases exist (Off may report 3, Transparency reports 8 = `00 01`) — OOv1.md:90-96; profiles.py:114-127.
- **[V]** [prior:gazz@abe70f4] SET ack `0x8404` byte 0 is status, not success: `00` on successful changes, but Pro 2 returned `0e` both for an already-active Off request (read-back matched) and a Transparency request while charging (read-back stayed Off); some sessions never send it — OOv1.md:84; docs/backend-cli.md:18.
- **[V]** [prior:gazz@abe70f4] Main ANC On does not reliably preserve the reported level (Smart retained in one sequence, returned Smart from a Deep start in another); explicit level commands verify both mode and level — OOv1.md:96-97; docs/devices/oneplus-buds-pro-2.md:19.
- **[V]** [prior:gazz@abe70f4] Persistent session: main On/Off/Transparency writes are accepted over the live authenticated monitoring connection with subscriptions active; `0x8404` and `0x810c` responses echo the request sequence, so responses are matched by command plus sequence — OOv1.md:165-171.
- **[V]** [prior:gazz@abe70f4] Settling race: original Pro acknowledged Transparency but an immediate fresh query returned the previous mode; a later read-only session showed Transparency. Fix: repeat fresh state queries (2 s deadline, max 32) without replaying SET — OOv1.md:173-181; session.py:202-228.
- **[V]** [prior:gazz@abe70f4] Native EQ: `0x010f` current, `0x0122` catalogue with `01 05`, `0x0406` select, `0x0418` update; acknowledgement is never success — a fresh current query plus catalogue re-read is required. Pro 2 custom IDs 4/5 declare six bands at 62/250/1000/4000/8000/16000 Hz, -6..+6 dB, signed whole-byte gains — OOv1.md:99-105, 133-140; docs/measurements/native-eq.md:23-27.
- **[V]** [prior:gazz@abe70f4] EQ state survived RFCOMM session teardown and a closed-case 60 s disconnect/reconnect on both models — OOv1.md:142-147; native-eq.md:34-40.

## Device coverage & evidence model

- **[V]** [prior:gazz@abe70f4] Product table: `060C14` Verified, `062014` Verified, other OnePlus/OPO products Experimental if discovered — docs/devices/compatibility.md:5-9.
- **[V]** [prior:gazz@abe70f4] Three labels: Verified (maintainer hardware), Community Tested (owner-supplied reproducible evidence), Experimental (protocol/service evidence only). Community testing never upgrades to maintainer-verified; write controls are gated to maintainer-verified profiles — compatibility.md:11-18; profiles.py:77-80.
- **[V]** [prior:gazz@abe70f4] Discovery requires a connected BlueZ device whose name contains `oneplus` or `oppo` and whose UUIDs contain one of the two OPO services; renamed devices may not match; OPPO is only an Experimental candidate; Realme is a research target, not an auto-match; BLE-only products unsupported — compatibility.md:20-24; src/oneplus_buds/bluez.py:31-35.
- **[V]** [prior:gazz@abe70f4] Unknown products may receive read-only queries over channel 15; no ANC writes; a failed query is not evidence of compatibility — compatibility.md:26-30.
- **[V]** [prior:gazz@abe70f4] Capability results separate presence (`capabilities`, `anc_modes`) from current boolean state (`feature_switches`); unrecognised IDs and unsolicited payloads are excluded to avoid leaking peer-device data — docs/backend-cli.md:22; src/oneplus_buds/models.py:39-63.
- **[V]** [prior:gazz@abe70f4] Write gating is explicit: ANC writes require `profile.verified` and the mode in `write_indices`; EQ preset writes require verified + `eq.write_verified`; custom EQ additionally `custom_write_verified` — session.py:176-177, 379-386, 320-321; profiles.py:83-145.
- **[M]** [prior:gazz@abe70f4] As at the pinned commit, no community-tested models are recorded — compatibility.md:11-12.
- **[U]** [prior:gazz@abe70f4] Pro 2 device record notes recovered HeyMelody registry declarations (fit testing, spatial audio, personalised noise, Zen mode, find-device) as not Linux support claims; only detection/identity/battery/noise control were verified in that phase — oneplus-buds-pro-2.md:52-54; oneplus-buds-pro.md:30-32.

## Worth adopting

- **[V]** [prior:gazz@abe70f4] Query-after-write as the only success criterion: send once, never replay; SET timeout may proceed to verification; bounded response-paced fresh queries — session.py:197-228; docs/measurements/anc-baseline.md:118-123.
- **[V]** [prior:gazz@abe70f4] Typed control results carry `verified`, `verification_queries`, and the raw `set_status`, so callers cannot mistake an ack for success — models.py:102-115; backend-cli.md:18.
- **[V]** [prior:gazz@abe70f4] One serialized RFCOMM owner per lifecycle; warm main-mode ANC reuses the authenticated session with no teardown, re-auth, or subscription restoration; explicit ANC levels, cold start, and one-shot CLI keep the conservative path — src/oneplus_buds/controller.py:16-24, 80-81, 119-132; anc-baseline.md:230-232.
- **[V]** [prior:gazz@abe70f4] On uncertain failure: close the session, invalidate cached ANC state, never replay the write; let poll/service recovery reconnect so a failed command's response is not delayed — controller.py:133-146; anc-baseline.md:106-111.
- **[V]** [prior:gazz@abe70f4] Notification discipline: subscribe only to advertised codes; redact unknown or unsolicited payloads into a bounded ignored counter; unmapped events are never promoted to state proof; recent event history is capped — session.py:148-165, 437-481; controller.py:273-306.
- **[V]** [prior:gazz@abe70f4] BlueZ availability watcher as a wake hint: generation-counted so arrivals are not lost and repeated signals cannot cause retry storms; fresh ObjectManager discovery remains authoritative; 1/2/4/8/16/30 s timer backoff retained as fallback; daemon restart clears cached hints — src/oneplus_buds/availability.py:9-33, 73-78; connection-lifecycle.md:101-107.
- **[V]** [prior:gazz@abe70f4] Optimized lifecycle: one RFCOMM socket retained from product identification through auth, essential battery/ANC queries, subscriptions, and monitoring; this removed a second socket and an observed 1 s EBUSY retry. The retained HELLO/REGISTER waits (~3.9 s) are the main remaining startup cost — connection-lifecycle.md:109-121, 143-148.
- **[M]** [prior:gazz@abe70f4] Measurement discipline: pinned baseline revision; named scenarios (cold service, arrival at empty service, same-device reconnect, cross-device switch); monotonic-ns phase tracer disabled by default; BlueZ supplies no controller-radio timestamp so latency starts at host signal receipt; failed/incomplete runs are retained, not averaged away; single samples are labelled phase-cost identifiers, not distributions — connection-lifecycle.md:3-5, 9-45, 75-97, 150-152.
- **[V]** [prior:gazz@abe70f4] Privacy-safe reports omit Bluetooth addresses, aliases, user/host identity, home paths, credentials, unrelated devices, and raw packets/frames — README.md:164-165; backend-cli.md:65.
- **[V]** [prior:gazz@abe70f4] Per-product ANC profile shape: `write_indices` plus `read_modes`/`read_levels` maps and read aliases, not one flat enum; default write sequence `0x42`, Off special-cased `0x40` — profiles.py:10-28, 88-93.

## Contradictions / cautions

- **[U]** [prior:gazz@abe70f4] Channel: their design hardcodes RFCOMM channel 15 with no SDP/channel-discovery phase — connection-lifecycle.md:52-54; transport.py:15. Our ETI81 uses channel 12, so do not import "channel 15" as family-wide (see our OQ-3).
- **[U]** [prior:gazz@abe70f4] Notifications: they used `0x0205` bulk subscribe with the exact advertised set on both reference models — OOv1.md:59-61. They never exercised our `0x0201` per-event register, so their work does not answer OQ-2.
- **[U]** [prior:gazz@abe70f4] `0x010d` works on Pro 2 but produced no response on original Pro even after registration — OOv1.md:41, 63. Feature-ID mappings are model-gated and must not be generalised from one model.
- **[U]** [prior:gazz@abe70f4] Handshake variants: newer BLE/Buds Pro 3 implementations use HELLO `0x0001` + REGISTER `0x0085`, while some RFCOMM registry projects claim normal state queries need no registration; they kept the legacy `0x0100` primer plus raw HELLO/REGISTER and require hardware to decide — OOv1.md:149-151.
- **[U]** [prior:gazz@abe70f4] Inner-length quirks are device-observed and tolerated only for `0x8100` and `0x0204`; do not loosen our frame decoder globally from their leniency — protocol.py:124-130.
- **[U]** [prior:gazz@abe70f4] Capability payload `00 bf 17 68 26 04` is unmapped and they explicitly refuse to infer dynamic capabilities from it — OOv1.md:41.
- **[U]** [prior:gazz@abe70f4] Internal doc inconsistency: the Pro 2 ANC table still labels main On as "(preserve level)" (oneplus-buds-pro-2.md:43) while the verified list says the resulting level is not stable enough to call preserve (oneplus-buds-pro-2.md:19). Trust the prose, not the table.
- **[V]** [prior:gazz@abe70f4] ANC write interpretation is strictly product-gated: community implementations for newer devices use a different set enum, so cross-model inheritance is unsafe — OOv1.md:67.
- **[V]** [prior:gazz@abe70f4] They deliberately tell readers not to repeat their baseline ANC cycles and to keep failed/incomplete runs as evidence — anc-baseline.md:236-242.
- **[U]** [prior:gazz@abe70f4] Registry declarations are not support: only identity, battery, and noise control were verified in their phase 1 — oneplus-buds-pro-2.md:52-54.

## Licence & reuse

- **[V]** [prior:gazz@abe70f4] MIT: LICENSE file present, GitHub API reports `spdx_id: MIT` at the pinned revision, README states plain MIT — README.md:207-209. Facts with attribution are fine; code reuse is legally permissible but our house rule keeps prior-art use to facts only.
- **[U]** [prior:gazz@abe70f4] Their own research inputs are licence-dirtier: OppoPods declares GPL-3.0 in its README but has no standalone licence file at the inspected commit; several others have no licence; they state no code was copied and only documented wire facts were used — docs/research/open-source.md:7-14, OOv1.md:155-162. Cite Gazz's observation, never funnel code from their unlicensed sources.
- **[M]** [prior:gazz@abe70f4] Provenance note claims no third-party source or raster assets are vendored; protocol code is independently implemented — open-source.md:27-30.

## Sources

- Clone: `git clone --depth 1 https://github.com/GazzasaurusRex/oneplus-buds-omarchy` → `/tmp/opencode/prior/gazz`; HEAD = `abe70f4b6e8f55cc8f6a4888c04ddead8a087e33` (commit dated 2026-09-16).
- Licence check: `curl https://api.github.com/repos/GazzasaurusRex/oneplus-buds-omarchy` on 2026-10-17 → `spdx_id: MIT`, default branch `main`, pushed 2026-09-16.
- Read: README.md; docs/protocols/OPOv1.md; docs/research/open-source.md; docs/devices/compatibility.md, oneplus-buds-pro.md, oneplus-buds-pro-2.md; docs/measurements/connection-lifecycle.md, native-eq.md, anc-baseline.md; docs/backend-cli.md; src/oneplus_buds/{models,availability,controller,profiles,session,protocol,bluez,transport}.py.
