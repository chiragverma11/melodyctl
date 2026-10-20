# Feature switch — `0x0403` → `0x8403`

- Direction: write; payload `[featureId, enable]` with enable `0`/`1`
  [hw:ETI81 2026-10-17].
- Verified on ETI81: feature `6` = **game (low-latency) mode**; success acks
  payload `00` [hw:ETI81 2026-10-17]. `melodyctl game on|off` uses this.
- No read-back: the device does not answer a query for feature-6 state, and
  ETI81 does not unlock the `0x010d` batch-status read either
  [hw:ETI81 2026-10-17]; prior art reads feature state back via `0x010d` on
  models that support it [prior:gazz@abe70f4] [untested]. The mode *is* reported
  as push event `5`, but only after a **gesture** that changes it (claim #48) —
  a `0x0403` write is not echoed [hw:ETI81 2026-10-19].
- Feature ids are **device data, not app constants**: the app parses
  `(featureType, status)` pairs from device frames and echoes the advertised
  id back in the switch — `FeatureSwitchInfo` [apk:FeatureSwitchInfo#<init>]
  [apk:FeatureSwitchInfo#getFeatureType]; the SDK surface has no id
  enumeration, so the ids are model data → OQ-7 resolved.
- Ids recorded so far: `6` = game / low-latency [hw:ETI81 2026-10-17]
  [prior:gazz@abe70f4]; `0x04` wear detection, `0x0b` hearing enhancement,
  `0x11` multipoint (dual-device), `0x18` high-quality audio, `0x05` unnamed
  [prior:gazz@abe70f4]; `0x1B` spatial sound [prior:buildscript@303997d]
  [prior:leaf@feb7b70]; `0x28` game-sound [prior:leaf@feb7b70]. Everything
  beyond `6` is [untested].
- Ack payload `0` = ok; anything else is treated as rejected by our CLI
  [hw:ETI81 2026-10-17].

Related: [commands/unmapped.md](unmapped.md) (`0x010d`, `0x0423`),
[opo-v1.md](../opo-v1.md).
