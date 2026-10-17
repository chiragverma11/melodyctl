# Feature switch — `0x0403` → `0x8403`

- Direction: write; payload `[featureId, enable]` with enable `0`/`1`
  [hw:ETI81 2026-10-17].
- Verified on ETI81: feature `6` = **game (low-latency) mode**; success acks
  payload `00` [hw:ETI81 2026-10-17]. `melodyctl game on|off` uses this.
- No read-back: the device does not push feature-6 state, and ETI81 does not
  unlock the `0x010d` batch-status read either [hw:ETI81 2026-10-17]; prior
  art reads feature state back via `0x010d` on models that support it
  [prior:gazz@abe70f4] [untested].
- Feature ids beyond 6 are **not yet interpreted** → OQ-7.
- Prior art: the same `[featureId, enable]` switch is generated for wear
  detection `0x04`, dual-device `0x11` and legacy spatial sound `0x1B`
  [prior:leaf@feb7b70] [untested]; the game switch may instead be `0x28`
  (game-sound) on models with game-sound entries [prior:leaf@feb7b70]
  [untested].
- Ack payload `0` = ok; anything else is treated as rejected by our CLI
  [hw:ETI81 2026-10-17].

Related: [commands/unmapped.md](unmapped.md) (`0x010d`, `0x0423`),
[opo-v1.md](../opo-v1.md).
