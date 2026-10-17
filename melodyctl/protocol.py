"""Protocol layer: framing, command ids, capability tables, decoders.

Pure functions, no I/O. Per-command reference: docs/protocol/."""
from __future__ import annotations


CMD_CAPS = 0x0100            # getRemoteCapability -> bitmap of supported groups
CMD_HELLO = CMD_CAPS
CMD_INFO = 0x0103
CMD_VERSION_GET = 0x0105     # status, count, then ASCII triples (component,kind,value)
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
    CMD_CAPS: "capability", CMD_INFO: "device_info", CMD_VERSION_GET: "version",
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


def decode_version_records(payload: bytes) -> list[dict]:
    """Decode the component version response payload (cmd 0x0105).

    Payload = status, count, then an ASCII CSV of ``count`` triples
    ``(component, kind, value)``. Components 1/2/3 are left/right/case; kind 2
    is the component firmware (kinds 1 and 4 are not yet interpreted).
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


