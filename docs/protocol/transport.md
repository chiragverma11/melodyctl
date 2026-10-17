# Transport — Bluetooth Classic RFCOMM/SPP

Control transport for HeyMelody-family earbuds. Everything below is from the
ETI81 unless tagged otherwise.

## Service identity

- The app discovers the control service via SDP using one of two UUIDs
  [apk:com.oplus.melody.btsdk]:
  - `0000079A-D102-11E1-9B23-00025B00A5A5` — ETI81's advertised uuid
    [hw:ETI81 2026-10-17] [wl:062410]
  - `00001107-D102-11E1-9B23-00025B00A5A5` — the other variant; prior art
    sees it on the original OnePlus Buds Pro [prior:gazz@abe70f4]
- All 85 whitelist entries advertise SPP (`supportSpp: true`) [wl]; only ETI81
  is verified by us [untested beyond ETI81].

## Channel

- The RFCOMM channel is whatever SDP reports; **12 on ETI81** (hardcoded in
  v1.2.x) [hw:ETI81 2026-10-17].
- Prior art hardcodes **15** [prior:gazz@abe70f4]; another project claims "12
  exclusively" [prior:osp54@3dbdc47] [untested]. Neither number is family-wide
  → OQ-3.
- SDP discovery is **not implemented** (the Python stdlib has no SDP API).
  Since Phase 4 the CLI probes on connect — 12, then 15, then a 1..30 sweep —
  and remembers the first channel that accepts; `--channel` /
  `MELODYCTL_CHANNEL` override it [hw:ETI81 2026-10-17] (probe path exercised
  on ETI81; other models untested). `tools/rfcomm_scan.py` browses and saves
  service records [untested].

## Session rules

- Only one RFCOMM connection at a time; a second attempt fails `busy`
  (errno 16) [hw:ETI81 2026-10-17].
- Idle buds stop answering: connect attempts report `Host is down`
  (errno 112/113); retrying wakes them [hw:ETI81 2026-10-17].
- On connect our CLI sends the `0x0100` capability frame as a hello and drains
  ~2 s before other traffic [hw:ETI81 2026-10-17] — see
  [commands/handshake.md](commands/handshake.md).
- Prior art keeps one persistent socket for a whole session and matches
  responses by `cmd` + `seq`; newer devices need extra raw HELLO/REGISTER
  frames before writes [prior:gazz@abe70f4] [untested] → OQ-6.
