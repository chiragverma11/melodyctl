# Devices — index

Status: live - profiles are generated from `whitelist.json`
(regen: `tools/build-profiles.py`).

Support ladder: **verified** (we ran on hardware) > **external** (named third
party's published evidence) > **untested** (whitelist-derived). Writes are
allowed only for `verified` profiles, or with an explicit `--force` (logged as
experimental).

| doc | status | content |
|---|---|---|
| `eti81-oppo-enco-buds.md` | live | our only verified device record |
| `coverage.md` | generated | whitelist-known vs implemented vs verified |

Verified today: only `062410` OPPO Enco Buds (ETI81). To upgrade a row, run
`melodyctl report` on the hardware and update its profile + claims.
