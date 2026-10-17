# Claims matrix

Every borrowed or observed fact, its source, and its verification status.
Updated in the same commit as any change that affects it.

Status legend:
**verified** = we ran it on hardware · **external** = third party's published evidence
(not our run) · **refuted** = checked and wrong · **untested** = derived, not verified.

| # | claim | tag | status | evidence / notes |
|---|---|---|---|---|
| 1 | ETI81 product id = `062410` (`0x0103` response `00 10 24 06`, 3 bytes LE) | `[hw:ETI81 2026-10-17]` | verified | findings `0x0105-is-remote-version` |
| 2 | `0x0105` = component version read: `status, count` + ASCII triples `(component, kind, value)`; kind 2 = firmware | `[hw:ETI81 2026-10-17]` `[prior:gazz]` | verified | ETI81 left 165 / right 165 / case 118; same shape as Gazz's Buds Pro (541/541/510) and Pro 2 (196/196/101) |
| 3 | `melodyctl eq` (≤ v1.2.1) mislabelled `0x0105` as EQ presets; ETI81 has **no EQ** | `[hw:ETI81 2026-10-17]` `[wl:062410]` | verified | whitelist entry has no `equalizer`/`equalizerMode`; EQ commands not unlocked by caps; fixed in v1.2.2 (`eq` → `fw`) |
| 4 | ANC query `0x010c` on ETI81 returns a single byte `02` (no bitmap) | `[hw:ETI81 2026-10-17]` | observation | meaning unknown → OQ-1 |
| 5 | ANC set `0x0404` payload `01 01 <bitmap>`, bit index = whitelist `protocolIndex`, byte count = `idx/8+1` | `[prior:leaf]` | untested | Leaf `CapabilityProfileFactory.ancPayload`; verify on first ANC device |
| 6 | ANC bitmap on product `060C14`: Off `01`, Transparency `02`, light ANC `04`, deep `08`, smart `10`; writes need legacy HELLO + `0x8500` REGISTER token dance | `[prior:gazz]` | external | their hardware 2026-09-02; model-specific, do not generalise |
| 7 | Notifications: query `0x0200` → `0x8200` (status, count, event ids); subscribe `0x0205` → `0x8205` + `0x0204` snapshot | `[prior:gazz]` `[prior:leaf]` | external | our CLI uses `0x0200` + `0x0201` register and works on ETI81 → OQ-2 |
| 8 | Battery: pairs `[component, raw]`; `raw & 0x7f` = %, bit 7 = charging; components 1/2/3 = L/R/case | `[hw:ETI81]` `[prior:*]` | verified | docs/protocol.md |
| 9 | Game mode = `0x0403` feature `6` | `[hw:ETI81]` | verified | docs/protocol.md |
| 10 | Whitelist: devices in `compatWhiteList` (85 entries); ids are 6 hex digits, 3 bytes LE on the wire | `[wl]` | verified | `whitelist.json` |
| 11 | RFCOMM channel: ETI81 = 12 (hardcoded in v1.2.x); prior art hardcodes 15 | `[hw:ETI81]` `[prior:*]` | partial | SDP discovery not yet proven → OQ-3 |
| 12 | Licences: Gazz MIT · osp54 MIT · buildscript MIT · Leaf-lsgtky **none** (all rights reserved) | `[prior:*]` | verified | `gh api repos/<r>/license`, 2026-10-17 |
| 13 | ETI81 whitelist entry: brand `oppo`, caps `batteryInfo` + `gameMode` only; no `noiseReductionMode`, no EQ keys at all; gesture `control` masks 516/612/8705/536 (match `docs/protocol.md`); uuid `0000079A-D102-11E1-9B23-00025B00A5A5`; SPP | `[wl:062410]` | verified | full entry dumped 2026-10-17; an earlier note of `customEqualizer: 1` was a misread of entry `06F450` (Buds3s) |
| 14 | Whitelist census: 85 entries, **all** advertise SPP; ANC 43, EQ modes 73 (custom EQ 38), game mode 67; brands `oppo` + `OnePlus` | `[wl]` | verified | generated: `docs/devices/coverage.md`, data: `melodyctl/data/profiles.json` (`tools/build-profiles.py`) |
| 15 | ANC is family-generic: `0x0404` payload `01 01 <bitmap>`, bit `i%8` in byte `i/8` where i = whitelist `protocolIndex`; modeType map 1 Off / 2 Transparency / 3 Light / 4 Deep / 5 NC / 6+10 Adaptive / 7 Smart / 8 Medium | `[prior:leaf@feb7b70]` | untested | Leaf derives it from its own 137-entry vendor whitelist; the same `protocolIndex` fields exist in ours |
| 16 | Session lifecycle: channel 15 default; ANC writes need legacy HELLO (2 s) + token REGISTER (1.5 s); `0x8404` ack is not proof of success — verify with a fresh-session `0x010c` query; persistent session reuse ~107-260 ms vs ~15 s reconnect | `[prior:gazz@abe70f4]` | external | their hardware; we adopt the query-after-write pattern |
| 17 | osp54 claims ">200 models" but ships a 20-id sample list; its ANC set uses only `01 01 {01,02,04}`; its UUID fallback is dead code (undefined name); it hardcodes a HeyMelody HMAC secret | `[prior:osp54@3dbdc47]` | external claim + caution | UX reference only; do not inherit claims or code |
| 18 | buildscript-dev verified only OnePlus Buds 3 (fw 127.127.101, id `063C14` — present in our whitelist as "OnePlus Buds 3"); all other models go through a "GENERIC_MODEL" untested path; polls every 4 s, dedupes, writes `status.json` atomically | `[prior:buildscript@303997d]` `[wl]` | external + partial | osp54's `045010` for the same device is **not** in the whitelist |
