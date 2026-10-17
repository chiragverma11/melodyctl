# ANC — query `0x010c`, set `0x0404`

ETI81 has **no ANC**: the whitelist entry declares no `noiseReductionMode`
[wl:062410]. Everything about mode bitmaps below is prior art for other
models and **untested** here.

## Query (`0x010c` → `0x810c`)

- Request payload `01 01` [hw:ETI81 2026-10-17] [prior:gazz@abe70f4]
  [prior:leaf@feb7b70].
- ETI81 answers a **single byte `02`** — no `01 01` bitmap window
  [hw:ETI81 2026-10-17] (see
  [captures/2026-10-17-eti81-baseline.md](captures/2026-10-17-eti81-baseline.md)).
  Meaning unknown → OQ-1; do not classify it as a mode.
- Prior art reads a `01 01 <bitmap>` window and takes the lowest set bit
  through the model's `protocolIndex` table [prior:leaf@feb7b70]
  [prior:gazz@abe70f4] [untested].

## Set (`0x0404` → `0x8404`)

- Family mechanism (Leaf): payload `01 01 <bitmap>`; bit = the whitelist
  `protocolIndex`, byte count = `idx/8 + 1`, LSB-first. Their `modeType` map:
  1 Off / 2 Transparency / 3 Light / 4 Deep / 5 NC / 6+10 Adaptive / 7 Smart /
  8 Medium [prior:leaf@feb7b70] [untested].
- Model bitmap, wrong to generalise: original Buds Pro `060C14` uses Off `01`,
  Transparency `02`, light `04`, deep `08`, smart `10` [prior:gazz@abe70f4].
- **Write-verify:** the `0x8404` ack is never proof. Gazz saw `0e` both for an
  already-active Off request (read-back matched) and for a Transparency
  request while the buds were charging (read-back stayed Off); some sessions
  send no ack at all. Success = a fresh `0x010c` re-query, repeated if the
  immediate reply is stale — never replay the write [prior:gazz@abe70f4]
  [untested].
- Newer devices need the legacy HELLO + token REGISTER handshake before
  writes [prior:gazz@abe70f4] [untested] → OQ-6.
- ETI81: `0x0404` is bitmap-unlocked but the device has no ANC, so our CLI
  never sends it [hw:ETI81 2026-10-17].

## In melodyctl (Phase 5)

- `melodyctl anc` sends `01 01` and prints the raw reply; on ETI81 it shows the
  uninterpreted `02` and notes the device has no ANC [hw:ETI81 2026-10-17].
- `melodyctl anc set <mode>` builds `01 01 <bitmap>` from the device's
  whitelist table: bit = `protocolIndex` of the chosen mode, names from
  `modeType` (1 off / 2 transparency / 3 light / 4 deep / 5 nc / 6+10
  adaptive / 7 smart / 8 medium) [wl] [prior:leaf@feb7b70]; `bit:N` selects a
  raw bit. After the write it re-queries `0x010c` ~1 s later and compares -
  the `0x8404` ack alone is not proof [prior:gazz@abe70f4].
- Writes go through the verified-profile gate; with no ANC hardware on hand
  the whole set path is [untested] (OQ-6: newer devices may need the auth
  dance).

Related: [opo-v1.md](../opo-v1.md) (master table),
[commands/unmapped.md](unmapped.md) (`0x0405`).
