# Framing — the OPOv1 `0xAA` wrapper

```
AA | LEN | 00 00 | cmd_lo | cmd_hi | seq | plen_lo | plen_hi | payload...
```

| field | meaning |
|---|---|
| `AA` | magic / sync byte |
| `LEN` | `7 + len(payload)`; counts the bytes after itself, so a frame is `LEN + 2` bytes |
| `00 00` | constant |
| `cmd` | 16-bit little-endian (`cmd_hi << 8 \| cmd_lo`) |
| `seq` | sequence byte |
| `plen` | payload length, 16-bit little-endian |
| `payload` | command-specific |

- Shape confirmed by our decoder and both prior-art implementations
  [hw:ETI81 2026-10-17] [prior:gazz@abe70f4] [prior:leaf@feb7b70].
- Responses use `cmd | 0x8000` (`0x0106` → `0x8106`); `0x0204` pushes arrive
  under the bare command [hw:ETI81 2026-10-17].

## Sequence numbers

- `seq` varies per request in our ETI81 session [hw:ETI81 2026-10-17]; our CLI
  increments a byte counter (hello uses `0x23`) and matches responses by
  command, not seq.
- Prior art: responses echo the request seq and matching is `cmd` + `seq`
  [prior:gazz@abe70f4]; Leaf auto-increments over `1..0xFE` and reserves
  `0xFF` for unsolicited broadcasts [prior:leaf@feb7b70] [untested].

## Lengths, reassembly, quirks

- Our CLI writes a single-byte `LEN` and refuses frames longer than 127
  (payload > 120); the parser reads a 7-bit varint for robustness. Prior art
  notes the official app also emits a varint [prior:leaf@feb7b70] [untested].
- No checksum appears in the observed/researched framing
  [prior:gazz@abe70f4].
- The receiver must scan for `0xAA` and split on the outer length; Leaf drops
  one byte and resyncs when a declared length looks impossible (< 7, or a
  frame over 512 bytes) [prior:leaf@feb7b70].
- **Gazz's quirk** [prior:gazz@abe70f4]: the inner `plen` can disagree with
  the payload bounded by the outer `LEN` — a `0x8100` reply reported an inner
  length one byte short, an unsolicited `0x0204` three bytes larger. The outer
  length still split concatenated frames exactly, so it is **authoritative**.
  Their caution: tolerate this per observed case, do not loosen a decoder
  globally.
- Raw ETI81 frame bytes are not committed yet — the baseline capture stores
  decoded payloads only [hw:ETI81 2026-10-17].
