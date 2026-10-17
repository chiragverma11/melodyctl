# Leaf-lsgtky/OppoPods — prior art notes

Pinned commit `feb7b70ccf6757852a0a58197d0d4839c10a296a` (master, committed 2026-10-04 per `git log -1`). Licence: NONE (all rights reserved) — facts only, never code.

## What it is

- Xposed/LSPosed module written in Kotlin for Xiaomi HyperOS (Android 15+) that provides system-level control of OPPO-family earbuds and mirrors them into the HyperOS/headset stack, described as building on HyperPods; `README.md:9-11`, `README.md:24-28`.
- Hooks four host processes, each with a distinct role: `com.android.bluetooth` for A2DP detection and the RFCOMM protocol, `com.milink.service` to mirror state into the HyperOS headset runtime, `com.xiaomi.bluetooth` for the connection popup/notification, `com.android.settings` for the headset detail page; `README.md:32-39`, scope list `app/src/main/resources/META-INF/xposed/scope.list:1-4`, module metadata `app/src/main/resources/META-INF/xposed/module.prop:1-4`.
- Single `:app` module; Compose + Miuix UI; libxposed API 102 with hot-reload entry; `AGENTS.md:5`, `AGENTS.md:24`, `AGENTS.md:36`.
- Two controller paths: Xposed-driven controller (`pods/RfcommController.kt`) and a standalone RFCOMM app controller (`pods/AppRfcommController.kt`) used when hooks are unavailable; `README.md:22`, `app/src/main/java/moe/chenxy/oppopods/pods/AppRfcommController.kt:180`, `.../AppRfcommController.kt:288`.
- Hooks register through one libxposed entry and a shared hook context/dispatcher, dispatching per owning package (process-name normalisation for hot reload); `app/src/main/java/moe/chenxy/oppopods/hook/HookEntry.kt:11-18`, `.../hook/HookEntry.kt:31-40`.
- Cross-process state is broadcast to the three system packages with device address/name extras; `app/src/main/java/moe/chenxy/oppopods/pods/RfcommController.kt:695-709`.
- Repo ships its own reverse-engineering notes from analysing the official HeyMelody app (JADX), including a full protocol writeup and per-feature findings; `AGENTS.md:15`, `docs/HeyMelody_Bluetooth_Protocol_Notes.md:1-3`, `docs/HeyMelody_Official_App_Protocol_Findings.md:1-3`.

## Device capability model (whitelist-driven)

- Core idea: a copy of the official HeyMelody cloud device whitelist is bundled as an asset and used to derive abilities; code comment attributes it to OPPO's `whiteList` array; `app/src/main/java/moe/chenxy/oppopods/pods/DeviceModelRegistry.kt:10-18`, `app/src/main/assets/device_models.json:1`.
- Asset census (own count of `device_models.json:1`): 137 entries with 137 distinct 6-hex product ids; brands oppo, OnePlus, realme; 70 entries declare `equalizerMode`, 45 `spatialTypes`, 41 `noiseReductionMode`, 47 `multiDevicesConnect`, 46 `wearDetection`, 36 `customEqualizer`, 8 `customEqFrequency`, 15 `gameSoundList`.
- Registry loads lazily/idempotently, sorts entries by name length descending so ambiguous name matches hit the more specific model first, and builds an id map that prefers entries carrying a `function` block; `DeviceModelRegistry.kt:34-63`.
- Identification precedence: exact product-id lookup first; fallback fuzzy Bluetooth-name match (exact, then model-name-in-device-name, then device-name-in-model-name), names normalised by lowercasing and stripping non-alphanumerics, fuzzy branches require at least five chars; `DeviceModelRegistry.kt:128-148`, `DeviceModelRegistry.kt:165-166`.
- Hook-process wrinkle: host process assets are not the module's, so the asset is reopened through the module's own package context with `CONTEXT_IGNORE_SECURITY`; `DeviceModelRegistry.kt:65-87`.
- Entry → capability parse reads `supportSpp`, `protocolType`, `spatialTypes`, `multiDevicesConnect`/`multiConnectFunctions`, `wearDetection`, game-mode signals, `customEqualizer`, EQ mode lists, `customEqFrequency`, `customEqMax`, and `noiseReductionMode`; a missing `function` block yields an unsupported/placeholder capability; `DeviceModelRegistry.kt:171-224`, `DeviceCapabilities.kt:63-95`.
- Stated design rule: model variation lives in the whitelist's `protocolIndex` (bit number) and never in new commands — capability parse and byte construction are separate layers; `DeviceModelRegistry.kt:14-18`, `app/src/main/java/moe/chenxy/oppopods/pods/CapabilityProfileFactory.kt:5-8`.
- ANC `modeType` → canonical key mapping: 1=off, 2=transparency, 3=light, 4=deep, 5=NC, 6 and 10=adaptive, 7=smart, 8=medium, unknown types become `ModeN`; `DeviceModelRegistry.kt:282-293`.
- `noiseReductionMode` children are split: noise-level children (smart/light/medium/deep) are registered as their own sendable entries for the level picker, while other children (e.g. sub-variants like adaptive transparency) only feed the bitmap index→name table so child-only adaptive devices do not wrongly expose an adaptive toggle; `DeviceModelRegistry.kt:334-364`.
- Main modes are always sent using the parent entry's `protocolIndex`; only a top-level adaptive entry sets the adaptive flag; `DeviceModelRegistry.kt:357-364`.
- Observed whitelist ANC shapes (analysis of `device_models.json:1`): 16× NC@1 with Smart/Light/Medium/Deep children and Off@0/Transparency@2; 9× NC@0/Off@1/Transparency@2 without children; 4× that shape plus adaptive@3; a few noise-level-first layouts with no NC. The registry flags a model as legacy ANC when NC is at bitmap index 0 and no children exist; `DeviceModelRegistry.kt:377-381`.
- With no model available, `AncModeParser` falls back to a static byte table and swaps NC/transparency semantics when the legacy flag is set; `app/src/main/java/moe/chenxy/oppopods/pods/Packets.kt:475-503`.
- Legacy ANC flag is carried into the generated profile; `CapabilityProfileFactory.kt:36-37`, `app/src/main/java/moe/chenxy/oppopods/pods/DeviceProfile.kt:46-47`.
- Game mode support is deliberately optimistic: only 16 of the bundled 137 entries mention game features, and the comment notes a hardware-confirmed device that declares none, so only an explicit negative counts; the real decision is deferred to a runtime batch probe of feature 0x06 vs 0x28; `DeviceModelRegistry.kt:255-272`.
- Feature id used for the game switch depends on presence of game-sound entries: has game sound → main switch 0x28, otherwise low-latency 0x06; `DeviceCapabilities.kt:102-104`.
- Spatial three-mode control requires the whitelist to declare `spatialTypes` containing head tracking (2); non-empty spatial types without head tracking degrade to a legacy on/off spatial-sound switch on feature 0x1B; `DeviceCapabilities.kt:96-100`, `CapabilityProfileFactory.kt:132-138`.
- The registry generates EQ presets from the whitelist by merging `equalizerMode`, `equalizerModeCompat` and `equalizerModeByVersion`, keyed by `protocolIndex`, display name resolved through a separate mode-type→name asset; `DeviceModelRegistry.kt:226-244`.
- EQ preset switching is uniform: command 0x0406 plus the protocol index as payload, regardless of model; `DeviceModelRegistry.kt:226-229`, `Packets.kt:75-77`.
- EQ mode-name assets map numeric mode type → localized marketing names (keys 0..40 observed), Chinese and English variants chosen by locale with Chinese fallback; `DeviceModelRegistry.kt:89-115`, `app/src/main/assets/eq_mode_names.json:2-44`, `app/src/main/assets/eq_mode_names.en.json:2-44`.
- `CapabilityProfileFactory` converts a capability set into a plain device profile (same type used by the rest of the send path), with generated ids prefixed `auto_` + product id and per-key commands plus UI visibility flags; `CapabilityProfileFactory.kt:15-54`.
- ANC payload derivation: `[01][01][bitmap bytes]`, with bit `(protocolIndex % 8)` set inside byte `protocolIndex / 8`, little-endian byte order; so index 1→`01 01 02`, index 2→`01 01 04`, index 11→`01 01 00 08`; `CapabilityProfileFactory.kt:58-71`.
- ANC command map keys to indices by canonical name (off/NC/transparency/adaptive) with a smart fallback when NC is absent; noise-level keys are only emitted when the model declares them; `CapabilityProfileFactory.kt:73-101`.
- Switch-style features (0x0403, payload `[featureId][00/01]`) are generated for game mode, wear detection 0x04, dual-device 0x11 and legacy spatial sound 0x1B, gated by whitelist flags; `CapabilityProfileFactory.kt:103-140`, `Packets.kt:233-238`.
- Query commands are declared model-independent (battery, ANC, EQ, EQ-all, status); `CapabilityProfileFactory.kt:154-164`.
- Profile resolution: manual model pick or AUTO mode (Bluetooth-name hint first, then exact rebuild on the product-id response; fallbacks maintained); `app/src/main/java/moe/chenxy/oppopods/pods/DeviceProfileStore.kt:111-144`, `RfcommController.kt:604-607`.
- Custom EQ metadata surfaces as: preset list, custom EQ visibility, whitelist band frequencies (fallback six official bands 62/250/1000/4000/8000/16000), and a possible device-side preset cap; `DeviceCapabilities.kt:37-55`, `DeviceCapabilities.kt:81-84`, `CapabilityProfileFactory.kt:45-48`.

## Protocol facts (commands, payload shapes)

- Outer frame the app writes: `AA` + total length (single byte here) + `00 00` + command 2 bytes LE + sequence + payload length 2 bytes LE + payload; total length counts 7 header bytes plus payload; `Packets.kt:6-11`, `Packets.kt:23-39`.
- Frame reader: scans for the `AA` sync byte, rejects totals below 7 or frames above 512 bytes by dropping one byte and rescanning, otherwise emits complete frames; `Packets.kt:164-204`.
- Sequence numbers are auto-incremented over 1..0xFE for live traffic, while the generated profiles use a fixed sequence 0xF0 for deterministic output; `Packets.kt:15-21`, `Packets.kt:41-57`, `DeviceProfile.kt:10-16`.
- Official app framing analysis says the same header exists as an inner packet, and that the outer length field is a 7-bit little-endian varint (multi-byte above 127); the project's writer still emits only one length byte; `docs/HeyMelody_Official_App_Protocol_Findings.md:89-144`, `Packets.kt:26-29`.
- Request/response convention: responses use request command OR 0x8000; sequence 0xFF is reserved for unsolicited earbud broadcasts and must not be used to match pending requests; `docs/HeyMelody_Official_App_Protocol_Findings.md:209-254`.
- Command ids used by the app (meanings where determinable):

| Cmd | Dir/meaning | Ref |
|---|---|---|
| `0x0100`/`0x8100` | handshake / remote capability query and response | `Packets.kt:293-296`, `docs/HeyMelody_Official_App_Protocol_Findings.md:645` |
| `0x0103`/`0x8103` | product id query; response payload `[status(1)][productId(3B LE)]`, status 0 and length 4 required, formatted `%06X` | `Packets.kt:249-252`, `Packets.kt:546-568` |
| `0x0106`/`0x8106` | battery query; response pairs `[index, raw]`, level `raw & 0x7F`, charging `raw & 0x80`, indexes 1/2/3 = left/right/case | `Packets.kt:220-225`, `Packets.kt:315-370` |
| `0x010C`/`0x810C` | ANC mode query with payload `01 01`; official also uses `03 01` (supported modes), `02 01`/`02 03`/`02 04` (switch items), `04 01` (intelligent NC) | `Packets.kt:277-280`, `docs/HeyMelody_Official_App_Protocol_Findings.md:652-655` |
| `0x010D`/`0x810D` | batch feature query (payload = count + feature ids); response is feature pairs or a structured status/count list | `Packets.kt:283-286`, `Packets.kt:693-762`, `docs/HeyMelody_Official_App_Protocol_Findings.md:480-558` |
| `0x010F`/`0x810F`, notify `0x0504` | current EQ preset query/response/change notification, payload `[status][eqId]` | `Packets.kt:254-260`, `Packets.kt:570-599` |
| `0x0122`/`0x8122` | all device-side EQ entries including custom presets; the app queries with payload `01 05` | `Packets.kt:71-73`, `Packets.kt:261-262`, `Packets.kt:601-669` |
| `0x012A` | official spatial-type query (not used by the app) | `docs/HeyMelody_Official_App_Protocol_Findings.md:666` |
| `0x0200`/`0x8200` | notification capability query/list of supported event codes `[status][count][codes...]` | `Packets.kt:297-304`, `Packets.kt:878-904` |
| `0x0204` | unsolicited event multiplex: type 0x01 battery, 0x03 ANC change, 0x04 fit detection, 0x06 connected-device list; official event table adds 0x01 battery, 0x02 wear, 0x03 ANC, 0x05 game, 0x06 multi-device, 0xF2 device list | `Packets.kt:282`, `Packets.kt:372-425`, `Packets.kt:811-876`, `docs/HeyMelody_Bluetooth_Protocol_Notes.md:264-275` |
| `0x0205`/`0x8205` | subscribe to notification codes (payload count + codes) | `Packets.kt:157-161`, `Packets.kt:298-304` |
| `0x0403`/`0x8403` | switch feature, payload `[featureId][00/01]` | `Packets.kt:269-270`, `Packets.kt:786-809` |
| `0x0404` | set ANC, form A `01 01 <bitmap>`; official form B `01 02 <level>`; noise levels smart=0x80, light=0x40, medium=0x20, deep=0x10 | `Packets.kt:267-268`, `Packets.kt:206-213`, `DeviceProfile.kt:118-124`, `docs/HeyMelody_Bluetooth_Protocol_Notes.md:156-175` |
| `0x0406` | set EQ preset `[protocolIndex]` | `Packets.kt:253-254`, `docs/HeyMelody_Official_App_Protocol_Findings.md:683` |
| `0x0418`/`0x8418` | create/update/delete custom EQ details | `Packets.kt:263-266`, `Packets.kt:79-155` |
| `0x0422`/`0x8422`, notify `0x0510` | set spatial audio type `[00 off/01 fixed/02 head tracking]` | `Packets.kt:271-272`, `Packets.kt:289-292`, `Packets.kt:765-784` |
| `0x0400`, `0x0401`, `0x0412`, `0x0420`, `0x0423`, `0x0427`, `0x042D` | official-only commands documented but not implemented: find earbuds, key functions, personal noise, game EQ, game-sound enable, prompt volume, tap strength | `docs/HeyMelody_Official_App_Protocol_Findings.md:677-698` |

- ANC response parsing (0x810C or 0x0204): locate a `01 01` window in the payload, read a little-endian 16-bit bitmap (second byte may be absent), take the lowest set bit, map through the whitelist index table; fallback static table: `10 00`=NC, `00 01`=transparency, `08 00`=off, `00 08`=adaptive, and a noise-level byte in `{0x80,0x40,0x20,0x10}` with zero second byte; `Packets.kt:439-540`.
- Smart-ANC auto-level notification: 0x0204 with type 0x03, key 0x04; bits 4/5/6 of the bitmap map to deep/medium/light; `Packets.kt:906-943`.
- Battery handling includes both the query response path and an unsolicited path (0x0204 type 0x01, count + index/value pairs); `Packets.kt:372-425`.
- Connected-device list (0x0204 type 0x06): per device, 6-byte MAC (reversed for display), profile flags, connection state (0x02 = connected), active flag, name length + name; `Packets.kt:820-876`.
- Custom EQ write payload (0x0418): action 1/2/3 (create/update/delete), min gain, max gain, entry id, name length + UTF-8 name (≤255 bytes), band count, then per band little-endian uint16 frequency + signed byte gain; written bands capped at 32, gains clamped to the declared min/max; `Packets.kt:120-155`.
- Custom EQ read (0x8122): `[status][count]` then per entry `[selected][min][max][eqId][nameLen][name UTF-8][bandCount][freq LE16, gain int8]*`; `Packets.kt:570-659`.
- Custom EQ band documentation: whitelist declares a 10-band list (31, 62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000) for the 8 models that carry it; otherwise the app falls back to the six official bands 62/250/1000/4000/8000/16000; band count and gain bounds are taken from the device response when saving; `DeviceCapabilities.kt:52-55`, `DeviceCapabilities.kt:41-50`, `Packets.kt:633-645`.
- Product id detection: after connecting, the controller sends handshake 0x0100, then product-id query 0x0103, then notification-capability 0x0200 and status queries; on reading a 0x8103 response it rebuilds the active profile from the whitelist, but only in AUTO mode (manual selection is not overridden), resets EQ state, broadcasts the new profile and re-sends status queries; `RfcommController.kt:660-677`, `RfcommController.kt:864-890`, `DeviceProfileStore.kt:132-144`.
- Connection method: first tries SPP service records with two HeyMelody UUIDs (`00001107-D102-11E1-9B23-00025B00A5A5`, `0000079A-D102-11E1-9B23-00025B00A5A5`), with a fallback of reflected fixed RFCOMM channel 15; `OppoRfcommSocketFactory.kt:16-76`, `README.md:43`.
- Notification init flow documented: query 0x0200, parse 0x8200, subscribe 0x0205, then send batch/battery/ANC queries; multi-device info requires subscription; `docs/HeyMelody_Bluetooth_Protocol_Notes.md:250-262`.
- The generated batch-status query is a fixed 11-feature blob (`0B 05 04 0B 11 13 18 06 1B 1C 27 28`), despite the project's own docs saying the official app builds this list dynamically from whitelist capability flags; `CapabilityProfileFactory.kt:160-163`, `docs/HeyMelody_Official_App_Protocol_Findings.md:548-558`.
- Feature id semantics documented: 0x04 wear-detection, 0x11 multi-device connect, 0x1B spatial types, 0x06 game/low-latency, 0x28 game-sound-related; a caution exists that decimal 28 = 0x1C (`controlAutoVolumeSupport`) differs from hex 0x28; `docs/HeyMelody_Official_App_Protocol_Findings.md:560-604`, `docs/HeyMelody_Official_App_Protocol_Findings.md:747`.
- Official command-group convention: 0x0100 queries, 0x0200 unsolicited/broadcast, 0x0400 settings/control; `docs/HeyMelody_Official_App_Protocol_Findings.md:258-286`.

## Worth adopting (as concepts, not code)

- Treat the vendor whitelist as data: parse into a capability object, then generate a per-device command profile with an `auto_`-style id, instead of hand-written per-model byte tables; `CapabilityProfileFactory.kt:3-12`, `CapabilityProfileFactory.kt:24-54`.
- Index-to-bitmap helper for feature payloads (ANC bit at `protocolIndex`, byte count from index/8) — a clean pattern for any bitmask-indexed setting; `CapabilityProfileFactory.kt:58-71`.
- Two-stage identification: pre-select by normalised device name, then correct on the product-id query response; long-name-first sorting avoids prefix ambiguity; `DeviceModelRegistry.kt:136-148`, `DeviceModelRegistry.kt:50-52`.
- Model capability gating drives both UI visibility and command emission, so unsupported features are never sent blindly; `CapabilityProfileFactory.kt:33-53`.
- Represent "legacy ANC bit ordering differs" as an explicit capability flag rather than heuristics spread over the codebase; `DeviceModelRegistry.kt:377-381`, `DeviceProfile.kt:46-47`.
- Model noise-level sub-modes (smart/light/medium/deep) as first-class selectable entries while sending only the parent mode bit for the main switch; `DeviceModelRegistry.kt:334-364`.
- Defer uncertain device support (game mode) to a runtime feature probe (0x06 vs 0x28) instead of trusting an incomplete cloud whitelist; `DeviceModelRegistry.kt:255-272`, `DeviceCapabilities.kt:102-104`.
- For custom EQ: keep per-band frequency lists and gain bounds device-sourced, with an official six-band default, and expose action-based create/update/delete; `DeviceCapabilities.kt:41-55`, `Packets.kt:79-155`.
- Protocol toolkit ideas: reserve seq 0xFF for unsolicited traffic, correlate responses via cmd|0x8000, negotiate notification codes (0x0200 → 0x0205) before relying on pushes, and read the outer length as a varint even if writing single-byte; `docs/HeyMelody_Official_App_Protocol_Findings.md:209-254`, `docs/HeyMelody_Bluetooth_Protocol_Notes.md:250-262`, `docs/HeyMelody_Official_App_Protocol_Findings.md:120-144`.
- Keep a byte-scanning frame reader tolerant of noise (resync on bad length) and a `01 01` window finder for payloads whose surrounding layout varies; `Packets.kt:164-204`, `Packets.kt:505-540`.
- Command meanings worth recording in melodyctl docs: 0x0103/0x0106/0x010C/0x010D/0x010F/0x0122 queries; 0x0403/0x0404/0x0406/0x0418/0x0422 setters; 0x0200/0x0204/0x0205/0x0510 notifications; `Packets.kt:247-305`.

## Contradictions / cautions

- The README claims GPL-3.0 (`README.md:105`, `README.md:207`) but the repository has no licence file; GitHub API reported `license: null` on 2026-10-17. A self-declared licence without the licence text cannot be relied on — treat the repo as all rights reserved.
- The bundled whitelist is a copy of the vendor app's cloud configuration (stated in code comments) — its provenance is OPPO/HeyMelody, not this project; do not reuse that asset even if the repo's licensing were clarified; `DeviceModelRegistry.kt:10-12`.
- The app still sends a fixed 11-feature batch query while its own docs conclude the official payload is whitelist-derived; any port should build the feature list per model; `CapabilityProfileFactory.kt:160-163`, `docs/HeyMelody_Official_App_Protocol_Findings.md:1259-1260`.
- The app writes 0x0122 with payload `01 05` whereas the official command table lists that query as payload-less; not reconciled in the docs; `Packets.kt:72-73`, `docs/HeyMelody_Official_App_Protocol_Findings.md:664`.
- ANC bitmap parsing takes the lowest set bit only; if a device reports the mode bit and a level bit together, interpretation may be lossy; `Packets.kt:453-471`.
- Legacy-ANC detection is a heuristic over whitelist shapes (NC at index 0 with no children), and some affected entries also carry adaptive at another index; verify per device; `DeviceModelRegistry.kt:377-381`.
- Game-mode default-to-supported will produce false positives for models that omit game entries; the 0x810D probe is the mitigating mechanism; `DeviceModelRegistry.kt:263-272`.
- Many behaviours are explicitly listed as needing hardware verification (noise-level `01 01` vs `01 02` form, 0x0204 event payload formats, UUID-vs-channel mapping, subscription flow); `docs/HeyMelody_Bluetooth_Protocol_Notes.md:355-366`, `docs/HeyMelody_Official_App_Protocol_Findings.md:1266-1281`.
- The frame writer emits a single total-length byte, so payloads over 127 bytes would diverge from the official varint form the docs describe; `Packets.kt:26-29`, `docs/HeyMelody_Official_App_Protocol_Findings.md:144`.
- The docs' evidence uses obfuscated class names from one analysed HeyMelody build; names and behaviours can drift across app versions; `docs/HeyMelody_Bluetooth_Protocol_Notes.md:3`.
- README feature tables are a partial subset of the docs (no custom EQ, noise levels, wear detection, dual device); do not treat the README as the full protocol spec; `README.md:49-59`, `Packets.kt:235-238`.

## Licence & reuse

- No licence file at the pinned commit; GitHub API: `license: null`. The README self-declares GPL-3.0 in two places, but a claim in prose is not a granted licence and the repo is all rights reserved by default (`README.md:105`, `README.md:207`, checked 2026-10-17).
- Consequently: do not copy any code, comments, doc prose, or bundled assets from this repo into melodyctl. It may only be cited as prior art with file:line references, as done here.
- The extracted facts (command ids, payload layouts, bitmap-index semantics, feature ids, identification flow) are functional protocol information; melodyctl must implement them independently from its own analysis or from its own device captures.
- The repo states it derives from HyperPods (its own README credits that project); any GPL obligations of the upstream project are not resolved by this repo's missing licence file; `README.md:11`.
- The bundled `device_models.json` is vendor-derived configuration; even for interop facts, prefer deriving capability data from melodyctl's own sources.

## Sources

- Clone: `gh repo clone Leaf-lsgtky/OppoPods -- --depth 1`; HEAD `feb7b70ccf6757852a0a58197d0d4839c10a296a` (2026-10-04, branch master). Cloned read-only into `/tmp/opencode/prior/leaf`; nothing in the repo was modified.
- `README.md:1-207`, `AGENTS.md:1-46`, `app/src/main/resources/META-INF/xposed/scope.list:1-4`, `app/src/main/resources/META-INF/xposed/module.prop:1-4`.
- `app/src/main/java/moe/chenxy/oppopods/pods/DeviceModelRegistry.kt:1-395`, `DeviceCapabilities.kt:1-117`, `CapabilityProfileFactory.kt:1-165`, `Packets.kt:1-944`, `DeviceProfile.kt:1-165`, `DeviceProfileStore.kt:90-149`, `RfcommController.kt:595-935`, `OppoRfcommSocketFactory.kt:1-106`, `AppRfcommController.kt:170-300`.
- Assets: `app/src/main/assets/device_models.json:1`, `eq_mode_names.json:1-45`, `eq_mode_names.en.json:1-45`.
- Hook skim: `hook/HookEntry.kt:1-40`, `hook/MiLinkServiceHook.kt:1-60`, `hook/SettingsDetailsHook.kt:1-50`, `hook/MiBluetoothToastHook.kt:1-35`, `hook/XiaomiBluetoothHeadsetIconGuard.kt:1-30`, `hook/HeadsetStateDispatcher.kt:1-35`.
- In-repo analysis docs: `docs/HeyMelody_Bluetooth_Protocol_Notes.md:1-366`, `docs/HeyMelody_Official_App_Protocol_Findings.md:1-1281`.
- Licence check: GitHub API `repos/Leaf-lsgtky/OppoPods` reports `license: null`; no `LICENSE`/`COPYING` file present in the tree (2026-10-17).
