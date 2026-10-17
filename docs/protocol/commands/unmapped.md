# Unmapped / not-advertised commands

Commands that are unlocked on ETI81 but whose behaviour is **not yet
interpreted** (OQ-8), plus commands ETI81 does not advertise at all. None of
these were sent by us; do not invent payload layouts.

## Unlocked on ETI81 (caps bitmap), not interpreted

| cmd | notes |
|---|---|
| `0x0107` | poll; not yet interpreted |
| `0x0109` | poll; not yet interpreted |
| `0x0400` | prior art's official command list places find-earbuds here [prior:leaf@feb7b70] [untested] |
| `0x0402` | write; not yet interpreted |
| `0x0405` | write; not yet interpreted |
| `0x0408` | write; not yet interpreted |
| `0x0409` | write; not yet interpreted |
| `0x0416` | write; not yet interpreted |

Unlocked status is from the ETI81 bitmap decode [hw:ETI81 2026-10-17]; the
poll/write grouping follows the `0x01xx` query / `0x04xx` control convention
[prior:leaf@feb7b70].

## Not advertised on ETI81

- `0x010d` batch status — no ETI81 support [hw:ETI81 2026-10-17]. Prior art:
  the request is a count + feature ids; replies are `(featureId, bool)` pairs
  or a structured status/count list [prior:leaf@feb7b70] [untested]. The
  original Buds Pro never answered it (even after registration); Buds Pro 2
  returned six pairs — `0x04` wear detection, `0x06` low latency, `0x0b`
  hearing enhancement, `0x11` multipoint, `0x18` high-quality audio, `0x05`
  unnamed [prior:gazz@abe70f4]. Model-gated; do not generalise.
- `0x0423` game *sound* — not advertised on ETI81 [hw:ETI81 2026-10-17];
  prior art lists a game-sound enable command [prior:leaf@feb7b70] [untested].
- `0x0406` EQ select — not advertised on ETI81, which has no EQ at all
  [wl:062410]. Prior art: payload is the preset `protocolIndex`
  [prior:leaf@feb7b70] [prior:gazz@abe70f4] [untested]; `melodyctl eq-set`
  stays experimental and other-models-only [hw:ETI81 2026-10-17].

Related: [opo-v1.md](../opo-v1.md) (master table),
[commands/feature-switch.md](feature-switch.md) (why `0x010d` matters for
read-back).
