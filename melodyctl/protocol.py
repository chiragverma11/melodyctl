"""Protocol layer: framing, command ids, capability tables, decoders.

Pure functions, no I/O. Per-command reference: docs/protocol/."""
from __future__ import annotations


CMD_CAPS = 0x0100            # getRemoteCapability -> bitmap of supported groups
CMD_HELLO = CMD_CAPS
CMD_INFO = 0x0103
CMD_VERSION_GET = 0x0105     # status, count, then ASCII triples (component,kind,value)
CMD_BATT_GET = 0x0106
CMD_GESTURES_GET = 0x0108
CMD_ANC_QUERY = 0x010c       # payload 01 01; replies type-tagged; ETI81 bare 02 = no bitmap (docs/protocol/commands/anc.md)
CMD_EQ_SET = 0x0406          # payload: [protocol_index]  (unsupported on ETI81)
CMD_EQ_CUSTOM_SET = 0x0418   # payload: custom EQ band data
CMD_GAMESOUND_SET = 0x0423   # payload: [type, enable]    (unsupported on ETI81)
CMD_GESTURES_SET = 0x0401    # payload: [count, (deviceType,button,action,function)*count]
CMD_KEYFUNC_SET = CMD_GESTURES_SET
CMD_SWITCH_FEATURE = 0x0403  # payload: [featureId, enable]  (feature 6 = game mode)
CMD_ANC_SET = 0x0404         # payload: 01 01 <bitmap>  (see docs/protocol/commands/anc.md)
CMD_NOTIFY_SUB = 0x0200      # subscribe to device notifications (no payload)
CMD_NOTIFY_REG = 0x0201      # register one event: payload [eventId]
CMD_NOTIFY_PUSH = 0x0204     # device push; payload[0] = event id

FEATURE_GAME_MODE = 6
NOTIFY_USER_INTERACTION = 0xF1   # 241: user tapped a bud
NOTIFY_NAMES = {1: "state_1", 2: "state_2", 241: "user_interaction", 242: "state_242"}

# ANC modeType names [prior:leaf@feb7b70]; 6 and 10 both render "adaptive".
# Types 11-13 (X4 children) have no published meaning - rendered as "typeN".
MODE_NAMES = {1: "off", 2: "transparency", 3: "light", 4: "deep", 5: "nc",
              6: "adaptive", 7: "smart", 8: "medium", 10: "adaptive"}

RESP_FLAG = 0x8000
COMPONENT = {1: "left", 2: "right", 3: "case"}
EAR = {1: "left", 2: "right", 4: "both"}
CMD_NAMES = {
    CMD_CAPS: "capability", CMD_INFO: "device_info", CMD_VERSION_GET: "version",
    CMD_BATT_GET: "battery", CMD_EQ_SET: "eq_set", CMD_EQ_CUSTOM_SET: "eq_custom_set",
    CMD_GAMESOUND_SET: "game_sound_set", CMD_GESTURES_SET: "gesture_set",
    CMD_GESTURES_GET: "gestures", CMD_SWITCH_FEATURE: "switch_feature",
    CMD_ANC_QUERY: "anc_query", CMD_ANC_SET: "anc_set",
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

# ---- gesture vocabulary (HeyMelody family) ----------------------------------
# Each whitelist `function.control` entry describes one gesture slot: an
# `action` on a `button` plus a `support` bitmask over the function presets
# below; the app shows the set bits as pickable functions
# [apk:Ha.a#c] [apk:Ha.a.<clinit>]. Preset order below is the app's UI order.
PRESET_NAMES = {
    0x1: "voice assistant", 0x2: "listening music", 0x4: "play/pause",
    0x8: "volume up", 0x10: "volume down", 0x20: "previous song",
    0x40: "next song", 0x80: "noise switch", 0x100: "play collection",
    0x200: "none", 0x400: "adjust volume", 0x800: "switch song",
    0x1000: "switch device", 0x2000: "game mode", 0x4000: "enter pairing",
    0x8000: "collect music", 0x10000: "zen mode", 0x20000: "AI summary",
    0x40000: "reject call", 0x80000: "answer/hang up",
    0x100000: "AI translation", 0x200000: "AI translation v2",
    0x400000: "clear pairing history", 0x800000: "spy tap",
    0x1000000: "GMN play/pause", 0x2000000: "GMN trigger",
}
PRESET_ORDER = [0x200, 0x80, 0x4, 0x20, 0x40, 0x1, 0x800000, 0x2, 0x8, 0x10,
                0x100, 0x400, 0x800, 0x1000, 0x2000, 0x4000, 0x8000, 0x10000,
                0x20000, 0x40000, 0x80000, 0x100000, 0x200000, 0x400000,
                0x1000000, 0x2000000]
# Preset bit -> wire `function` code [apk:Ha.a#b]. 0x4000 (enter pairing) and
# 0x400000 (clear pairing history) have no settable wire code in the app.
_PRESET_WIRE = {
    0x1: 3, 0x2: 2, 0x4: 1, 0x8: 11, 0x10: 12, 0x80: 8, 0x100: 9,
    0x200: 0, 0x400: 7, 0x800: 10, 0x1000: 13, 0x2000: 17, 0x8000: 22,
    0x10000: 18, 0x20000: 25, 0x40000: 28, 0x80000: 29,
    0x100000: 26, 0x200000: 26, 0x800000: 32,
    0x1000000: 34, 0x2000000: 35,
}


def preset_wire(bit: int, oneplus_branch: bool = False) -> int | None:
    """Wire function code for a whitelist `support` bit, or None when unmapped.

    ``oneplus_branch`` follows the app's product check, which is true only for
    the exact names "OnePlus Buds" and "OnePlus Buds Z": previous/next shift
    down one code there [apk:Ha.a#b] [apk:d#I].
    """
    if bit == 0x20:
        return 4 if oneplus_branch else 5
    if bit == 0x40:
        return 5 if oneplus_branch else 6
    return _PRESET_WIRE.get(bit)


def mask_presets(mask: int) -> list[tuple[int, str]]:
    """(bit, name) for every preset set in a slot's `support` mask, UI order."""
    return [(bit, PRESET_NAMES.get(bit, hex(bit)))
            for bit in PRESET_ORDER if mask & bit]


def mask_wires(mask: int, oneplus_branch: bool = False) -> list[int]:
    """Wire function codes allowed by a slot's `support` mask, UI order."""
    out: list[int] = []
    for bit in PRESET_ORDER:
        if mask & bit:
            code = preset_wire(bit, oneplus_branch)
            if code is not None and code not in out:
                out.append(code)
    return out


# Wire `function` codes [apk:Ha.a#b]. 4/5/6 are product-dependent: code 4 only
# occurs on the OnePlus branch, and there code 5 means "next song" (see
# preset_wire / function_name).
FUNCTION_NAMES = {
    0: "none", 1: "play/pause", 2: "listening music", 3: "voice assistant",
    4: "previous song (OnePlus branch)", 5: "previous song", 6: "next song",
    7: "adjust volume", 8: "noise switch", 9: "play collection",
    10: "switch song", 11: "volume up", 12: "volume down",
    13: "switch device", 17: "game mode", 18: "zen mode",
    22: "collect music", 25: "AI summary", 26: "AI translation",
    27: "AI real-time translation", 28: "reject call", 29: "answer/hang up",
    32: "spy tap", 34: "GMN play/pause", 35: "GMN trigger",
}


def function_name(code: int, oneplus_branch: bool = False) -> str:
    """Human name for a wire function code on a given product branch."""
    if oneplus_branch:
        if code == 4:
            return "previous song"
        if code == 5:
            return "next song"
        if code == 6:
            return "f6"  # unused on the OnePlus branch
    return FUNCTION_NAMES.get(code, f"f{code}")


# Button ids [apk:Ha.a#g]: 1 tap/touch area, 2/3 neckband volume keys,
# 5 middle button, 6 both volume keys (long press). Only 1 and 5 occur in the
# whitelist control tables [wl].
BUTTON_NAMES = {1: "tap/touch", 2: "volume + button", 3: "volume - button",
                5: "middle button", 6: "volume +/- keys"}
# Gesture action ids [apk:Ha.a#g]; 5-8 and 16-20 appear on models that
# advertise slide/pinch slots (see each device's whitelist control table).
ACTION_NAMES = {
    1: "single tap", 2: "double tap", 3: "triple tap", 4: "long press",
    5: "slide", 6: "super-long press", 7: "slide up", 8: "slide down",
    11: "long press (alt)", 16: "single pinch", 17: "double pinch",
    18: "triple pinch", 20: "long pinch", 25: "middle-button long press",
    27: "long press (alt)",
}

# Human-friendly aliases for the gesture-set positional args (case-insensitive).
# Numeric values are always accepted too, so these only add names.
EAR_ALIASES = {"left": 1, "l": 1, "right": 2, "r": 2, "both": 4, "b": 4}
BUTTON_ALIASES = {"tap": 1, "touch": 1, "middle": 5, "mid": 5}
ACTION_ALIASES = {
    "single": 1, "single tap": 1, "single_tap": 1,
    "double": 2, "double tap": 2, "double_tap": 2,
    "triple": 3, "triple tap": 3, "triple_tap": 3,
    "long": 4, "long press": 4, "long_press": 4,
    "slide": 5, "super long": 6, "super-long": 6, "super long press": 6,
    "slide up": 7, "slide_up": 7, "slide down": 8,
    "pinch": 16, "single pinch": 16, "double pinch": 17,
    "triple pinch": 18, "long pinch": 20,
}
FUNCTION_ALIASES = {
    "none": 0, "off": 0,
    "play": 1, "pause": 1, "play/pause": 1, "playpause": 1,
    "listening": 2, "listening music": 2,
    "assistant": 3, "voice": 3, "va": 3,
    "prev": 5, "previous": 5, "previous song": 5,
    "next": 6, "next song": 6,
    "adjust volume": 7,
    "noise": 8, "noise switch": 8,
    "play collection": 9, "collection": 9,
    "switch song": 10,
    "vol+": 11, "volup": 11, "up": 11, "vol-": 12, "voldown": 12, "down": 12,
    "switch device": 13,
    "game": 17, "game mode": 17,
    "zen": 18, "zen mode": 18,
    "collect": 22, "collect music": 22,
    "summary": 25, "ai summary": 25,
    "translate": 26, "translation": 26, "ai translation": 26,
    "real-time translation": 27,
    "reject": 28, "reject call": 28,
    "answer": 29, "hang up": 29, "answer/hang up": 29,
    "spy": 32, "spy tap": 32,
    "gmn": 34, "gmn play/pause": 34,
    "gmn trigger": 35,
}


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


def decode_user_interaction(b: bytes, oneplus_branch: bool = False) -> dict:
    """Decode a user-interaction event body: [deviceType,button,action,function,scene]."""
    if len(b) < 5:
        return {}
    return {
        "device_type": b[0],
        "ear": EAR.get(b[0], str(b[0])),
        "button": b[1],
        "action": b[2],
        "function": b[3],
        "function_name": function_name(b[3], oneplus_branch),
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


def decode_product_id(payload: bytes) -> str | None:
    """Decode the 0x0103 reply: [status][3-byte little-endian product id]."""
    if len(payload) < 4:
        return None
    return payload[1:4][::-1].hex().upper()


def anc_bitmap(protocol_index: int) -> bytes:
    """Leaf-style ANC bitmap: bit idx%8 of byte idx//8; length idx//8 + 1."""
    n = protocol_index // 8 + 1
    b = bytearray(n)
    b[protocol_index // 8] |= 1 << (protocol_index % 8)
    return bytes(b)


def decode_anc_bitmap(bitmap: bytes) -> int | None:
    """Lowest set bit index of an ANC bitmap, or None when no bit is set."""
    for i, byte in enumerate(bitmap):
        if byte:
            return i * 8 + ((byte & -byte).bit_length() - 1)
    return None


def decode_gestures(payload: bytes, oneplus_branch: bool = False) -> list[dict]:
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
            "function_name": function_name(function, oneplus_branch),
        })
    return out


def decode_version_records(payload: bytes) -> list[dict]:
    """Decode the component version response payload (cmd 0x0105).

    Payload = status, count, then an ASCII CSV of ``count`` triples
    ``(component, kind, value)``. Components 1/2/3 are left/right/case; kind 1
    = hardware, kind 2 = running firmware, kind 3 = backup, kind 4 = vendor
    code.
    Observed on ETI81: left 165, right 165, case 118.
    """
    records: list[dict] = []
    if len(payload) < 2:
        return records
    count = payload[1]
    text = payload[2:].decode("ascii", "replace")
    nums: list[int] = []
    for tok in text.split(","):
        tok = tok.strip()
        if tok.lstrip("-").isdigit():
            nums.append(int(tok))
    for i in range(0, min(len(nums), count * 3) - 2, 3):
        records.append({"component": nums[i], "kind": nums[i + 1],
                        "value": nums[i + 2]})
    return records


def _fmt_versions(records: list[dict]) -> str:
    by = {(r["component"], r["kind"]): r["value"] for r in records}
    parts = [f"{name}={by[(comp, 2)]}" for comp, name in COMPONENT.items()
             if (comp, 2) in by]
    return "  ".join(parts) or "(no version data)"


def _fmt_battery(b: dict) -> str:
    parts = []
    for name in ("left", "right", "case"):
        if name in b:
            bolt = "+" if b[name]["charging"] else ""
            parts.append(f"{name}={b[name]['level']}%{bolt}")
    return "  ".join(parts)


# ---- friendly, single-line errors -------------------------------------------
# errno -> (code, hint). The CLI never dumps a traceback to users, and widgets
# can map a failure to a short message instead of showing raw stderr.
_ERRNO_HINTS: dict[int, tuple[str, str]] = {
    16: ("busy", "Another app (e.g. HeyMelody) is using the earbuds; only one "
                 "connection is allowed at a time."),
    19: ("no_adapter", "No Bluetooth adapter found - is Bluetooth enabled?"),
    110: ("timeout", "No response from the earbuds (timed out)."),
    111: ("refused", "The earbuds refused the connection (off, out of range, or "
                     "not paired)."),
    112: ("unreachable", "The earbuds are unreachable (off or out of range)."),
    113: ("unreachable", "The earbuds are unreachable (off or out of range)."),
}


