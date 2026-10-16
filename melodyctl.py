#!/usr/bin/env python3
"""melodyctl - control OPPO Enco Buds (ETI81) over the OPOv1 RFCOMM channel.

Reads individual Left / Right / Case battery percentages and reads/writes the
earbud touch-gesture (key function) configuration on Linux. The wire protocol
is the same one HeyMelody (com.heytap.headset) uses for OPPO/OnePlus SPP buds;
this tool is verified only on the OPPO Enco Buds (ETI81).

Protocol (reverse engineered from HeyMelody's com.oplus.melody.btsdk):
  Transport : Bluetooth Classic RFCOMM, channel 12
  Framing   : OPOv1 wrapper, little-endian fields
      AA | LEN | 00 | 00 | cmd_lo | cmd_hi | seq | plen_lo | plen_hi | payload...
      cmd  = cmd_hi<<8 | cmd_lo          (e.g. battery query = 0x0106)
      resp = cmd | 0x8000                (e.g. battery reply = 0x8106)
      LEN  = 7 + len(payload)            (single-byte length for small frames)

  Commands used here (16-bit "cmd" ids, poll = 0x01xx, set = 0x04xx):
      0x0100 capability  0x0103 device info  0x0105 EQ read
      0x0106 battery     0x0108 gestures     0x0401 set gesture
  The device's capability bitmap (reply to 0x0100) is authoritative for which
  commands are supported. On ETI81 EQ (0x0406) is read-only and game *sound*
  (0x0423) is unsupported, but game *mode* is a feature switch:
      0x0403  [featureId, enable]     featureId 6 = game mode
  Touch gestures are readable (0x0108) and writable (0x0401). Async device
  events need subscribe (0x0200) then register (0x0201 [eventId]); pushes
  arrive on 0x0204 with payload[0] = event id (0xF1 = user gesture event).
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time

ADDR_DEFAULT = (os.environ.get("MELODYCTL_ADDR")
                or os.environ.get("ENCO_ADDR", "6C:0D:E1:5F:DB:4D"))
RFCOMM_CH = 12

# ---- command ids (little-endian on the wire) --------------------------------
CMD_CAPS = 0x0100            # getRemoteCapability -> bitmap of supported groups
CMD_HELLO = CMD_CAPS
CMD_INFO = 0x0103
CMD_EQ_GET = 0x0105
CMD_BATT_GET = 0x0106
CMD_GESTURES_GET = 0x0108
CMD_EQ_SET = 0x0406          # payload: [protocol_index]  (unsupported on ETI81)
CMD_EQ_CUSTOM_SET = 0x0418   # payload: custom EQ band data
CMD_GAMESOUND_SET = 0x0423   # payload: [type, enable]    (unsupported on ETI81)
CMD_GESTURES_SET = 0x0401    # payload: [count, (deviceType,button,action,function)*count]
CMD_KEYFUNC_SET = CMD_GESTURES_SET
CMD_SWITCH_FEATURE = 0x0403  # payload: [featureId, enable]  (feature 6 = game mode)
CMD_NOTIFY_SUB = 0x0200      # subscribe to device notifications (no payload)
CMD_NOTIFY_REG = 0x0201      # register one event: payload [eventId]
CMD_NOTIFY_PUSH = 0x0204     # device push; payload[0] = event id

FEATURE_GAME_MODE = 6
NOTIFY_USER_INTERACTION = 0xF1   # 241: user tapped a bud
NOTIFY_NAMES = {1: "state_1", 2: "state_2", 241: "user_interaction", 242: "state_242"}

RESP_FLAG = 0x8000
COMPONENT = {1: "left", 2: "right", 3: "case"}
EAR = {1: "left", 2: "right", 4: "both"}
CMD_NAMES = {
    CMD_CAPS: "capability", CMD_INFO: "device_info", CMD_EQ_GET: "eq_read",
    CMD_BATT_GET: "battery", CMD_EQ_SET: "eq_set", CMD_EQ_CUSTOM_SET: "eq_custom_set",
    CMD_GAMESOUND_SET: "game_sound_set", CMD_GESTURES_SET: "gesture_set",
    CMD_GESTURES_GET: "gestures", CMD_SWITCH_FEATURE: "switch_feature",
}

# p026b8.a.f14745a: capability bit index -> command ids it unlocks.
CAP_GROUPS = [
    [261], [262], [263], [264, 1025, 1046], [265], [1024], [1026], [1027],
    [268, 1028], [1029], [1030, 271], [1031], [], [1032], [1033], [], [],
    [276], [], [1038, 1037, 277, 278], [1039], [1040, 281], [517], [3840], [],
    [280, 1041], [282, 1042], [284, 1043], [], [274, 1035], [286, 287, 1045],
    [1037], [], [289, 1047], [290, 1048], [1049], [285, 1044], [291, 1050],
    [292, 1051], [293, 1052, 295, 1053, 1055], [1057, 35, 36, 34, 294, 297],
    [61185], [61186], [61187, 1054], [1056], [28], [], [1058, 298], [61188],
    [1059, 299], [], [1060], [61190], [], [], [1061, 302, 1062], [303],
    [1063, 304], [305, 1064], [1065, 306], [20], [1069, 307], [1070], [61191],
    [61192, 310, 1075], [61193], [1073, 308], [1074, 309, 1077], [279],
]

# Gesture "function" codes (from HeyMelody N.b / Ha.a.b).
# NOTE: codes 4/5/6 are product-dependent. HeyMelody's d.I(product) is true
# only for "OnePlus Buds" / "OnePlus Buds Z"; ETI81 is neither, so the OPPO
# branch below applies:
#   code 4 : previous song, OnePlus only (maps to a mask, unused on OPPO)
#   code 5 : previous song on OPPO  / next song on OnePlus
#   code 6 : next song on OPPO
FUNCTION_NAMES = {
    0: "none", 1: "play/pause", 2: "resume", 3: "voice assistant",
    4: "previous (OnePlus only)", 5: "previous song", 6: "next song",
    7: "adjust volume", 8: "noise reduction", 9: "play collection",
    10: "switch song", 11: "volume up", 12: "volume down",
    13: "switch device", 17: "game mode", 18: "zen mode",
    22: "collect music", 25: "AI summary", 26: "ai assist", 27: "translation",
    28: "reject call", 29: "answer/end call", 32: "quick tap",
    34: "GMN play/pause", 35: "GMN trigger",
}
# Button ids: 1 = tap/touch control, 6 = slide/pinch (force) group.
BUTTON_NAMES = {1: "tap", 6: "long-press"}
# Gesture "button action" ids (N9.k): 1=single 2=double 3=triple 4=long-press.
ACTION_NAMES = {1: "single tap", 2: "double tap", 3: "triple tap", 4: "long press"}
# Allowed function ids per action for ETI81 (from whitelist support masks 062410):
#   action1 support 516  = 512|4         -> {none, play/pause}
#   action2 support 612  = 512|4|32|64   -> {none, play/pause, previous(5), next(6)}
#   action3 support 8705 = 8192|512|1    -> {none, voice assistant(3), game mode(17)}
#   action4 support 536  = 512|16|8      -> {none, volume up(11), volume down(12)}
ACTION_FUNCTIONS = {
    1: [0, 1], 2: [0, 1, 5, 6], 3: [0, 3, 17], 4: [0, 11, 12],
}

# Human-friendly aliases for the gesture-set positional args (case-insensitive).
# Numeric values are always accepted too, so these only add names.
EAR_ALIASES = {"left": 1, "l": 1, "right": 2, "r": 2, "both": 4, "b": 4}
BUTTON_ALIASES = {"tap": 1, "touch": 1, "long": 6, "long-press": 6, "long_press": 6}
ACTION_ALIASES = {
    "single": 1, "single tap": 1, "single_tap": 1,
    "double": 2, "double tap": 2, "double_tap": 2,
    "triple": 3, "triple tap": 3, "triple_tap": 3,
    "long": 4, "long press": 4, "long_press": 4,
}
FUNCTION_ALIASES = {
    "none": 0, "off": 0, "play": 1, "pause": 1, "play/pause": 1, "playpause": 1,
    "assistant": 3, "voice": 3, "va": 3,
    "prev": 5, "previous": 5, "last": 5, "next": 6,
    "vol+": 11, "volup": 11, "up": 11, "vol-": 12, "voldown": 12, "down": 12,
    "game": 17, "game mode": 17,
}


def _resolve_int(value: str, aliases: dict[str, int], kind: str) -> int:
    """Accept a number (any base) or a friendly name for a gesture argument."""
    key = value.strip().lower()
    if key in aliases:
        return aliases[key]
    try:
        return int(key, 0)
    except ValueError:
        opts = ", ".join(sorted(aliases))
        raise argparse.ArgumentTypeError(
            f"invalid {kind} {value!r}; use a number or one of: {opts}") from None


def _gesture_tables() -> str:
    """Render the gesture value tables + examples (used by --list and -h)."""
    out = ["value tables  (ETI81 = OPPO Enco Buds, whitelist product 062410)", ""]
    out.append("  ear     which bud        1=left, 2=right, 4=both (4 is split into per-ear writes)")
    out.append("  button  which control    1=tap/touch (the only one on ETI81), 6=slide/pinch (not on ETI81)")
    out.append("  action  which gesture on that button:")
    for a in sorted(ACTION_NAMES):
        out.append(f"                          {a} = {ACTION_NAMES[a]}")
    out.append("  function  what the gesture does (allowed combos on ETI81):")
    for a in sorted(ACTION_FUNCTIONS):
        fns = ", ".join(f"{f}={FUNCTION_NAMES.get(f, '?')}" for f in ACTION_FUNCTIONS[a])
        out.append(f"                          action {a} ({ACTION_NAMES[a]}): {fns}")
    out.append("")
    out.append("  Names are accepted as well as numbers, e.g. ear=left, action=triple,")
    out.append("  function=assistant. Any other combo is rejected by the device.")
    out.append("")
    out.append("examples:")
    out.append("  melodyctl gesture-set left tap single none      # left single tap -> none")
    out.append("  melodyctl gesture-set left tap double prev      # left double tap -> previous")
    out.append("  melodyctl gesture-set left tap triple assistant # left triple tap -> assistant")
    out.append("  melodyctl gesture-set right tap triple game     # right triple tap -> game mode")
    out.append("  melodyctl gesture-set both tap long vol+        # both long press -> volume up")
    return "\n".join(out)


def frame(cmd: int, payload: bytes = b"", seq: int = 0) -> bytes:
    """Build a single-frame OPOv1 packet (payload must be <= 120 bytes)."""
    body = bytes([cmd & 0xFF, (cmd >> 8) & 0xFF, seq & 0xFF,
                  len(payload) & 0xFF, (len(payload) >> 8) & 0xFF]) + payload
    length = len(body) + 2
    if length > 127:
        raise ValueError("payload too large for a single frame")
    return bytes([0xAA, length, 0x00, 0x00]) + body


def parse_frames(data: bytes) -> list[dict]:
    """Parse a stream of OPOv1 frames into dicts."""
    out: list[dict] = []
    i = 0
    n = len(data)
    while i < n:
        if data[i] != 0xAA:
            i += 1
            continue
        j = i + 1
        length = 0
        shift = 0
        while j < n:
            b = data[j]
            length |= (b & 0x7F) << shift
            j += 1
            shift += 7
            if not (b & 0x80):
                break
        if j + length > n:
            break
        # length counts from j: [x][y] then body
        body = data[j + 2:j + length]
        if len(body) >= 5:
            cmd = body[0] | (body[1] << 8)
            seq = body[2]
            plen = body[3] | (body[4] << 8)
            out.append({
                "cmd": cmd,
                "seq": seq,
                "payload": body[5:5 + plen],
                "raw": data[i:j + length],
            })
        i = j + length
    return out


class Buds:
    def __init__(self, addr: str = ADDR_DEFAULT, timeout: float = 10.0) -> None:
        self.addr = addr
        self.timeout = timeout
        self.sock: socket.socket | None = None
        self.seq = 0x20

    def __enter__(self) -> "Buds":
        self.connect()
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    def connect(self) -> None:
        s = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
        s.settimeout(self.timeout)
        s.connect((self.addr, RFCOMM_CH))
        self.sock = s
        self._hello()

    def close(self) -> None:
        if self.sock is not None:
            try:
                self.sock.close()
            finally:
                self.sock = None

    def _drain(self, wait: float) -> bytes:
        assert self.sock is not None
        end = time.time() + wait
        buf = bytearray()
        self.sock.settimeout(0.3)
        while time.time() < end:
            try:
                chunk = self.sock.recv(512)
                if not chunk:
                    break
                buf += chunk
                end = time.time() + 0.5
            except socket.timeout:
                continue
            except OSError:
                break
        return bytes(buf)

    def _hello(self) -> None:
        assert self.sock is not None
        self.sock.sendall(frame(CMD_HELLO, b"", 0x23))
        self._drain(2.0)

    def _next_seq(self) -> int:
        self.seq = (self.seq + 1) & 0xFF
        return self.seq

    def send(self, cmd: int, payload: bytes = b"", wait: float = 2.5) -> list[dict]:
        """Send one command, return the parsed response frames that match it."""
        assert self.sock is not None, "not connected"
        seq = self._next_seq()
        self.sock.sendall(frame(cmd, payload, seq))
        frames = parse_frames(self._drain(wait))
        want = cmd | RESP_FLAG
        return [f for f in frames if f["cmd"] == want]

    def raw(self, pkt: bytes, wait: float = 2.5) -> bytes:
        assert self.sock is not None, "not connected"
        self.sock.sendall(pkt)
        return self._drain(wait)

    # ---- high level --------------------------------------------------------
    def battery(self) -> dict:
        """Return {left,right,case} levels plus charging flags."""
        for f in self.send(CMD_BATT_GET):
            p = f["payload"]
            if len(p) < 2:
                continue
            # payload = [status/0x00][count][ (dev, charging<<7|level) * count ]
            count = p[1]
            out: dict[str, dict] = {}
            for k in range(count):
                idx = 2 + k * 2
                if idx + 1 >= len(p):
                    break
                dev = p[idx]
                val = p[idx + 1]
                out[COMPONENT.get(dev, f"id{dev}")] = {
                    "level": val & 0x7F,
                    "charging": bool(val & 0x80),
                }
            if out:
                return out
        raise ValueError("no battery response")

    def eq_presets(self) -> list[dict]:
        """Decode the EQ preset table (cmd 0x0105 response)."""
        for f in self.send(CMD_EQ_GET):
            return decode_eq_table(f["payload"])
        return []

    def set_eq(self, index: int) -> list[dict]:
        return self.send(CMD_EQ_SET, bytes([index & 0xFF]))

    def set_game_sound(self, gtype: int, enable: bool) -> list[dict]:
        return self.send(CMD_GAMESOUND_SET, bytes([gtype & 0xFF, 1 if enable else 0]))

    def caps(self) -> set[int]:
        """Return the set of command ids the device advertises."""
        for f in self.send(CMD_CAPS):
            return decode_caps(f["payload"])
        return set()

    def gestures(self) -> list[dict]:
        """Return the touch-gesture (key function) table."""
        for f in self.send(CMD_GESTURES_GET):
            return decode_gestures(f["payload"])
        return []

    def set_gesture(self, ear: int, button: int, action: int, function: int) -> list[dict]:
        """Assign ``function`` to (ear, button, action). Ack payload 0x00 = ok.

        ear 4 ("both") is expanded into two per-ear writes, since the device
        rejects combined-ear writes for some actions.
        """
        ears = [1, 2] if ear == 4 else [ear]
        out: list[dict] = []
        for e in ears:
            payload = bytes([1, e & 0xFF, button & 0xFF, action & 0xFF, function & 0xFF])
            out += self.send(CMD_GESTURES_SET, payload)
        return out

    def set_game_mode(self, enable: bool) -> list[dict]:
        """Toggle game (low-latency) mode: feature switch 0x0403, feature 6."""
        return self.send(CMD_SWITCH_FEATURE, bytes([FEATURE_GAME_MODE, 1 if enable else 0]))

    # ---- notifications -----------------------------------------------------
    def notify_caps(self) -> list[int]:
        """Subscribe (0x0200) and return the event ids the device can push."""
        for f in self.send(CMD_NOTIFY_SUB, wait=2.0):
            p = f["payload"]
            if len(p) >= 2:
                return list(p[2:2 + p[1]])
        return []

    def register_notify(self, events: list[int]) -> dict[int, int | None]:
        """Register event ids (0x0201). Returns {eventId: ackStatus}."""
        out: dict[int, int | None] = {}
        for e in events:
            r = self.send(CMD_NOTIFY_REG, bytes([e & 0xFF]), wait=1.5)
            out[e] = r[0]["payload"][0] if r and r[0]["payload"] else None
        return out


def decode_user_interaction(b: bytes) -> dict:
    """Decode a user-interaction event body: [deviceType,button,action,function,scene]."""
    if len(b) < 5:
        return {}
    return {
        "device_type": b[0],
        "ear": EAR.get(b[0], str(b[0])),
        "button": b[1],
        "action": b[2],
        "function": b[3],
        "function_name": FUNCTION_NAMES.get(b[3], f"f{b[3]}"),
        "scene": b[4],
    }


def decode_caps(payload: bytes) -> set[int]:
    """Decode the capability bitmap reply: payload = [status][bitmap...]."""
    if len(payload) < 2:
        return set()
    bmp = payload[1:]
    out: set[int] = set()
    for i, ids in enumerate(CAP_GROUPS):
        if i < len(bmp) * 8 and (bmp[i // 8] >> (i % 8)) & 1:
            out.update(ids)
    return out


def decode_gestures(payload: bytes) -> list[dict]:
    """Decode the gesture reply: [status][count][ (ear,button,action,function) * count ]."""
    if len(payload) < 2:
        return []
    count = payload[1]
    out: list[dict] = []
    for i in range(count):
        off = 2 + i * 4
        if off + 4 > len(payload):
            break
        ear, button, action, function = payload[off:off + 4]
        out.append({
            "ear": EAR.get(ear, str(ear)),
            "device_type": ear,
            "button": button,
            "button_name": BUTTON_NAMES.get(button, str(button)),
            "action": action,
            "action_name": ACTION_NAMES.get(action, f"action {action}"),
            "function": function,
            "function_name": FUNCTION_NAMES.get(function, f"f{function}"),
        })
    return out


def decode_eq_table(payload: bytes) -> list[dict]:
    """Decode the EQ preset response payload.

    Observed payload = b'\\x00\\x09' + b'1,1,9,1,2,165,1,4,0,2,1,0,...' (ASCII CSV).
    The CSV is a flat list of 9-number groups, one per preset; the first number
    of each group is the preset index used by ``eq-set``.
    """
    text = payload[2:].decode("ascii", "replace")
    nums: list[int] = []
    for tok in text.split(","):
        tok = tok.strip()
        if tok.lstrip("-").isdigit():
            nums.append(int(tok))
    presets = []
    for i in range(0, len(nums) - 8, 9):
        g = nums[i:i + 9]
        presets.append({"index": g[0], "values": g[1:]})
    return presets


def _fmt_battery(b: dict) -> str:
    parts = []
    for name in ("left", "right", "case"):
        if name in b:
            bolt = "+" if b[name]["charging"] else ""
            parts.append(f"{name}={b[name]['level']}%{bolt}")
    return "  ".join(parts)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="melodyctl", description="OPPO Enco Buds control (OPOv1/RFCOMM)")
    ap.add_argument("-a", "--addr", default=ADDR_DEFAULT, help="buds Bluetooth address")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_bat = sub.add_parser("battery", help="read Left/Right/Case battery")
    p_bat.add_argument("--json", action="store_true", help="flat {left,right,case} levels (for widgets)")
    p_bat.add_argument("--json-full", action="store_true", help="levels + charging flags")

    p_mon = sub.add_parser("monitor", help="poll battery continuously")
    p_mon.add_argument("-i", "--interval", type=float, default=30.0)
    p_mon.add_argument("--json", action="store_true")

    sub.add_parser("devinfo", help="query device info (raw)")

    p_caps = sub.add_parser("caps", help="show device capability bitmap / supported commands")
    p_caps.add_argument("--json", action="store_true")

    p_g = sub.add_parser("gestures", help="read the touch-gesture (key function) table")
    p_g.add_argument("--json", action="store_true")

    p_gs = sub.add_parser(
        "gesture-set", help="assign a function to a gesture (see --list)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=_gesture_tables())
    p_gs.add_argument("ear", nargs="?", type=lambda v: _resolve_int(v, EAR_ALIASES, "ear"),
                      help="which bud: 1=left, 2=right, 4=both")
    p_gs.add_argument("button", nargs="?", type=lambda v: _resolve_int(v, BUTTON_ALIASES, "button"),
                      help="which control: 1=tap (6=slide/pinch, not on ETI81)")
    p_gs.add_argument("action", nargs="?", type=lambda v: _resolve_int(v, ACTION_ALIASES, "action"),
                      help="which gesture: 1=single 2=double 3=triple 4=long press")
    p_gs.add_argument("function", nargs="?", type=lambda v: _resolve_int(v, FUNCTION_ALIASES, "function"),
                      help="what it does, e.g. play/pause, prev, next, vol+, assistant, game, none")
    p_gs.add_argument("-f", "--force", action="store_true",
                      help="send even if the action/function combo is not advertised for this model")
    p_gs.add_argument("-l", "--list", action="store_true",
                      help="print the gesture value tables and exit (no device connection)")

    p_eq = sub.add_parser("eq", help="read EQ preset table")
    p_eq.add_argument("--json", action="store_true")
    p_eq.add_argument("--raw", action="store_true")

    p_eqs = sub.add_parser("eq-set", help="set EQ preset by protocol index")
    p_eqs.add_argument("index", type=lambda v: int(v, 0))

    p_game = sub.add_parser("game", help="toggle game (low-latency) mode")
    p_game.add_argument("state", choices=["on", "off"])

    sub.add_parser("watch", help="subscribe to device events (tap the buds to map gestures)")

    p_raw = sub.add_parser("raw", help="send a raw hex packet")
    p_raw.add_argument("hex")

    args = ap.parse_args(argv)

    try:
        if args.cmd == "battery":
            with Buds(args.addr) as conn:
                b = conn.battery()
            if args.json:
                print(json.dumps({k: b[k]["level"] for k in b}))
            elif args.json_full:
                print(json.dumps(b))
            else:
                print(_fmt_battery(b))
            return 0

        if args.cmd == "monitor":
            with Buds(args.addr) as conn:
                while True:
                    try:
                        b = conn.battery()
                        line = json.dumps(b) if args.json else _fmt_battery(b)
                        print(f"{time.strftime('%H:%M:%S')}  {line}", flush=True)
                    except Exception as exc:  # noqa: BLE001
                        print(f"{time.strftime('%H:%M:%S')}  ! {exc}", flush=True)
                    time.sleep(args.interval)
            return 0

        if args.cmd == "devinfo":
            with Buds(args.addr) as conn:
                for f in conn.send(CMD_INFO):
                    print(f"cmd=0x{f['cmd']:04x} payload={f['payload'].hex(' ').upper()}")
                else:
                    pass
            return 0

        if args.cmd == "caps":
            with Buds(args.addr) as conn:
                caps = conn.caps()
            if args.json:
                print(json.dumps(sorted(caps)))
            else:
                print("supported cmd ids:", ", ".join(f"0x{c:04x}" for c in sorted(caps)) or "(none)")
                feats = []
                if CMD_BATT_GET in caps:
                    feats.append("battery")
                if CMD_GESTURES_GET in caps and CMD_GESTURES_SET in caps:
                    feats.append("gestures")
                if CMD_SWITCH_FEATURE in caps:
                    feats.append("game-mode")
                if CMD_EQ_SET in caps:
                    feats.append("eq-set")
                if CMD_GAMESOUND_SET in caps:
                    feats.append("game-sound")
                print("features:", ", ".join(feats) or "(none)")
                if CMD_EQ_SET not in caps:
                    print("note: EQ is read-only on this model.")
            return 0

        if args.cmd == "gestures":
            with Buds(args.addr) as conn:
                g = conn.gestures()
            if args.json:
                print(json.dumps(g))
            else:
                for r in g:
                    print(f"{r['ear']:<5} {r['action_name']:<12} -> "
                          f"{r['function_name']:<16} (f{r['function']})")
            return 0

        if args.cmd == "gesture-set":
            if args.list:
                print(_gesture_tables())
                return 0
            missing = [n for n, v in (("ear", args.ear), ("button", args.button),
                                      ("action", args.action), ("function", args.function))
                       if v is None]
            if missing:
                print(f"gesture-set: missing {'/'.join(missing)}; "
                      f"run 'melodyctl gesture-set --list' to see values", file=sys.stderr)
                return 2

            problems = []
            if args.ear not in EAR:
                problems.append(f"ear {args.ear} is not 1=left/2=right/4=both")
            if args.button not in BUTTON_NAMES:
                problems.append(f"button {args.button} is not 1=tap/6=slide-pinch")
            if args.button == 1:
                allowed = ACTION_FUNCTIONS.get(args.action)
                if allowed is None:
                    problems.append(
                        f"action {args.action} is not a gesture slot on ETI81 "
                        f"(valid: {', '.join(str(a) for a in sorted(ACTION_FUNCTIONS))})")
                elif args.function not in allowed:
                    problems.append(
                        f"function {args.function} ({FUNCTION_NAMES.get(args.function, '?')}) "
                        f"is not allowed for {ACTION_NAMES.get(args.action)}; allowed: "
                        + ", ".join(f"{f}={FUNCTION_NAMES.get(f, '?')}" for f in allowed))
            if problems and not args.force:
                for p in problems:
                    print(f"error: {p}", file=sys.stderr)
                print("       re-run with --force to send anyway.", file=sys.stderr)
                return 2
            for p in problems:
                print(f"warning: {p} (sending anyway due to --force)", file=sys.stderr)

            with Buds(args.addr) as conn:
                resp = conn.set_gesture(args.ear, args.button, args.action, args.function)
            if not resp:
                print("no ack (command unsupported or rejected)", file=sys.stderr)
                return 1
            acks = [r["payload"][0] if r["payload"] else None for r in resp]
            ok = bool(acks) and all(a == 0 for a in acks)
            fn = FUNCTION_NAMES.get(args.function, args.function)
            print(f"set ear={EAR.get(args.ear, args.ear)} button={BUTTON_NAMES.get(args.button, args.button)} "
                  f"action={ACTION_NAMES.get(args.action, args.action)} "
                  f"function={fn} -> ack {acks} ({'ok' if ok else 'rejected'})")
            return 0 if ok else 1

        if args.cmd == "eq":
            with Buds(args.addr) as conn:
                frames = conn.send(CMD_EQ_GET)
            if not frames:
                print("no EQ response", file=sys.stderr)
                return 1
            payload = frames[0]["payload"]
            if args.raw:
                print(payload.hex(" ").upper())
            elif args.json:
                print(json.dumps(decode_eq_table(payload)))
            else:
                print(json.dumps(decode_eq_table(payload), indent=2))
            return 0

        if args.cmd == "eq-set":
            with Buds(args.addr) as conn:
                resp = conn.set_eq(args.index)
            print(f"set EQ index={args.index} -> " +
                  (", ".join(f"0x{f['cmd']:04x}:{f['payload'].hex(' ').upper()}" for f in resp) or "no ack"))
            return 0 if resp else 1

        if args.cmd == "game":
            with Buds(args.addr) as conn:
                resp = conn.set_game_mode(args.state == "on")
            code = resp[0]["payload"][0] if resp and resp[0]["payload"] else None
            print(f"game mode {args.state} -> ack {code} "
                  f"({'ok' if code == 0 else 'rejected'})")
            return 0 if code == 0 else 1

        if args.cmd == "watch":
            with Buds(args.addr) as conn:
                caps = conn.notify_caps()
                print("pushable events:", ", ".join(
                    f"{e}({NOTIFY_NAMES.get(e, '?')})" for e in caps) or "(none)")
                conn.register_notify(caps)
                print("watching for events - tap/triple-tap/hold the buds. Ctrl-C to stop.", flush=True)
                while True:
                    for f in parse_frames(conn._drain(1.0)):
                        if f["cmd"] != CMD_NOTIFY_PUSH:
                            continue
                        p = f["payload"]
                        if not p:
                            continue
                        if p[0] == NOTIFY_USER_INTERACTION:
                            d = decode_user_interaction(p[1:])
                            print(f"  GESTURE   ear={d.get('ear'):<5} button={d.get('button')} "
                                  f"action={d.get('action')} -> {d.get('function_name')} "
                                  f"({d.get('function')}) scene={d.get('scene')}", flush=True)
                        else:
                            print(f"  EVENT {NOTIFY_NAMES.get(p[0], hex(p[0]))}: "
                                  f"{p.hex(' ').upper()}", flush=True)
            return 0

        if args.cmd == "raw":
            with Buds(args.addr) as conn:
                print(conn.raw(bytes.fromhex(args.hex.replace(" ", ""))).hex(" ").upper())
            return 0
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
