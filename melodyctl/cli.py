"""Command-line interface: argparse surface, command handlers, output formatting."""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import time
import traceback

from . import __version__, devices
from .errors import MelodyctlError, classify_error, emit_error
from .protocol import ACTION_ALIASES, ACTION_NAMES, BUTTON_ALIASES, BUTTON_NAMES, CMD_ANC_QUERY, CMD_BATT_GET, CMD_CAPS, CMD_EQ_SET, CMD_GAMESOUND_SET, CMD_GESTURES_GET, CMD_GESTURES_SET, CMD_INFO, CMD_NOTIFY_REG_MULTI, CMD_SWITCH_FEATURE, CMD_VERSION_GET, EAR, EAR_ALIASES, FUNCTION_ALIASES, FUNCTION_NAMES, MODE_NAMES, NOTIFY_NAMES, _fmt_battery, _fmt_devices, _fmt_status, _fmt_versions, anc_bitmap, decode_anc_bitmap, decode_caps, decode_product_id, decode_version_records, function_name, mask_presets, mask_wires, preset_wire
from .transport import ADDR_DEFAULT, Buds

# Failures worth sitting through when --reconnect is given: the device is
# asleep / cased / out of range, which is exactly the case a watcher must ride
# out. 'busy', 'no_adapter' and an unclassified error need attention, so they
# still abort.
_RETRY_CODES = {"disconnected", "unreachable", "timeout", "refused", "no_channel"}


def _retry_log(attempt: int, exc: BaseException, delay: float) -> None:
    """Say why we are waiting, without flooding: first try, then ~every minute."""
    if attempt == 1:
        print(f"  [{time.strftime('%H:%M:%S')}] {exc}", file=sys.stderr, flush=True)
    if attempt == 1 or attempt % 4 == 0:
        print(f"  ... still waiting: retrying every {delay:.0f}s (Ctrl-C to stop)",
              file=sys.stderr, flush=True)


def _connect_retrying(conn: Buds, retry: bool, delay: float = 2.0,
                      cap: float = 15.0) -> None:
    """Connect, waiting for the device to come back when ``retry`` is set."""
    attempt = 0
    while True:
        attempt += 1
        try:
            conn.connect()
            return
        except Exception as exc:  # noqa: BLE001 - users get one clean line
            code, _ = classify_error(exc)
            if not retry or code not in _RETRY_CODES:
                raise
            _retry_log(attempt, exc, delay)
            time.sleep(delay)
            delay = min(delay * 2, cap)


@contextlib.contextmanager
def _session(addr: str, retry: bool, cap: float = 15.0):
    """A Buds session that can wait for the device to appear, then closes."""
    conn = Buds(addr)
    _connect_retrying(conn, retry, cap=cap)
    try:
        yield conn
    finally:
        conn.close()


def _watch_line(ev: dict, json_mode: bool) -> None:
    """Print one watched event: a JSON object, or a timestamped human line."""
    if json_mode:
        ev["ts"] = time.time()
        print(json.dumps(ev), flush=True)
        return
    stamp = time.strftime("%H:%M:%S")
    if "battery" in ev:
        label, detail = "BATTERY", _fmt_battery(ev["battery"])
    elif "status" in ev:
        label, detail = "STATUS", _fmt_status(ev["status"])
    elif "interaction" in ev:
        d = ev["interaction"]
        label = "GESTURE"
        detail = (f"ear={d.get('ear'):<5} button={d.get('button')} "
                  f"action={d.get('action')} -> {d.get('function_name')} "
                  f"({d.get('function')}) scene={d.get('scene')}")
    elif "devices" in ev:
        label, detail = "DEVICES", _fmt_devices(ev["devices"])
    elif "game" in ev:
        g = ev["game"]
        label = "GAME"
        detail = ("on" if g.get("on") else "off") if g else "(no state byte)"
    else:
        label, detail = "EVENT", f"{ev['event']}: {ev.get('raw', '')}"
    print(f"  [{stamp}] {label:<9} {detail}", flush=True)


def _watch_info(message: str, json_mode: bool) -> None:
    """Human chatter for `watch`: under --json it goes to stderr, so stdout
    stays a pure JSON stream a daemon can pipe straight into a parser."""
    print(message, file=sys.stderr if json_mode else sys.stdout, flush=True)


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


def _product_id(value: str) -> str:
    """Normalise a product id (``062410``, ``0x062410``, ``62410``) to 6 hex digits."""
    key = value.strip().lower().removeprefix("0x").replace(":", "").replace(" ", "")
    if not key or any(c not in "0123456789abcdef" for c in key) or len(key) > 6:
        raise argparse.ArgumentTypeError(
            f"invalid product id {value!r}; expected six hex digits, e.g. 062410")
    return key.zfill(6).upper()


def _gesture_tables() -> str:
    """Render the gesture vocabulary tables (used by --list and -h)."""
    out = ["gesture values  (HeyMelody-family vocabulary; which combos a device",
           "               accepts comes from its whitelist profile and is checked",
           "               against the connected device when you write)", ""]
    out.append("  ear       which bud       1=left, 2=right, 4=both (4 is split into per-ear writes)")
    out.append("  button    which control   1=tap/touch, 2/3=neckband volume keys,")
    out.append("                            5=middle button, 6=volume keys (long press)")
    out.append("  action    which gesture on that button:")
    for a in sorted(ACTION_NAMES):
        out.append(f"                            {a} = {ACTION_NAMES[a]}")
    out.append("  function  what the gesture does (wire codes; 4/5/6 shift on the")
    out.append("            two 'OnePlus Buds'/'OnePlus Buds Z' models):")
    for f in sorted(FUNCTION_NAMES):
        out.append(f"                            {f} = {FUNCTION_NAMES[f]}")
    out.append("")
    out.append("  Names are accepted as well as numbers, e.g. ear=left, action=triple,")
    out.append("  function=assistant. Combos the device's profile does not allow are")
    out.append("  rejected before sending (--force bypasses the check).")
    out.append("")
    out.append("examples:")
    out.append("  melodyctl gesture-set left tap single none       # left single tap -> none")
    out.append("  melodyctl gesture-set left tap double prev      # left double tap -> previous")
    out.append("  melodyctl gesture-set left tap triple assistant # left triple tap -> assistant")
    out.append("  melodyctl gesture-set right tap triple game     # right triple tap -> game mode")
    out.append("  melodyctl gesture-set both tap long vol+        # both long press -> volume up")
    out.append("  melodyctl gesture-set left pinch double play    # left double pinch -> play/pause")
    return "\n".join(out)


def _gesture_json(profile: dict | None, product_id: str | None) -> dict:
    """Machine-readable gesture vocabulary, plus one product's allowed combos.

    Deliberately offline: the slots come from the whitelist profile, not the
    device, so a widget that already ran `melodyctl device --json` can render
    the per-model editor without opening a second RFCOMM link. `function: null`
    marks a preset the app offers but has no wire code for (so the CLI can
    never write it either).
    """
    op = devices.oneplus_branch(profile)
    slots: list[dict] = []
    for slot in devices.gesture_slots(profile):
        mask = slot.get("support")
        if not mask:
            continue
        slots.append({
            "button": slot.get("button") or 1,
            "action": slot.get("action"),
            "ear": slot.get("ear"),
            "functions": [{"bit": bit, "name": preset, "function": preset_wire(bit, op)}
                          for bit, preset in mask_presets(mask)],
        })
    return {
        "product_id": product_id,
        "device": profile.get("name") if profile else None,
        "brand": profile.get("brand") if profile else None,
        "verified": devices.is_verified(product_id),
        "oneplus_branch": op,
        "vocabulary": {
            "ears": [{"id": k, "name": v} for k, v in sorted(EAR.items())],
            "buttons": [{"id": k, "name": v} for k, v in sorted(BUTTON_NAMES.items())],
            "actions": [{"id": k, "name": v} for k, v in sorted(ACTION_NAMES.items())],
            "functions": [{"id": k, "name": function_name(k, op)}
                          for k in sorted(FUNCTION_NAMES)],
        },
        "slots": slots,
    }


def _gesture_write_problems(profile: dict | None, args) -> list[str]:
    """Device-specific pre-send checks against the whitelist control table.

    Returns human problems; empty = fine. Unknown devices (no profile) and
    profiles without a control table are not checked here - the write gate
    still applies.
    """
    if profile is None:
        return []
    slots = devices.gesture_slots(profile)
    if not slots:
        return []
    name = profile.get("name") or "this device"
    slot = devices.gesture_slot(profile, args.button, args.action)
    if slot is None:
        actions = sorted({s.get("action") for s in slots if s.get("action") is not None})
        return [f"{name} does not advertise a button {args.button} action {args.action} "
                f"gesture slot (its whitelist slots use actions: "
                + ", ".join(str(a) for a in actions) + ")"]
    mask = slot.get("support")
    if not mask:
        return [f"{name}: the action {args.action} slot has no function mask in the "
                f"whitelist, so function {args.function} cannot be checked"]
    op = devices.oneplus_branch(profile)
    pairs: dict[int, str] = {}
    for bit, pname in mask_presets(mask):
        code = preset_wire(bit, op)
        if code is not None:
            pairs.setdefault(code, pname)
    if args.function not in pairs:
        shown = ", ".join(f"{c}={n}" for c, n in sorted(pairs.items()))
        return [f"{name}: action {ACTION_NAMES.get(args.action, args.action)} allows "
                f"{shown}; function {args.function} "
                f"({function_name(args.function, op)}) is not one of them"]
    return []


def _identify(conn: Buds) -> str | None:
    """Product id from 0x0103 ('062410'), or None when the device stays silent."""
    resp = conn.send(CMD_INFO)
    return decode_product_id(resp[0]["payload"]) if resp else None


def _write_gate(pid: str | None, action: str, force: bool,
                json_mode: bool = False) -> bool:
    """Enforce the write gate: verified profiles only. False = refused (printed)."""
    refusal = devices.write_refusal(pid, action)
    if refusal is None:
        return True
    if force:
        if not json_mode:
            print(f"warning: {refusal} sending anyway (--force)", file=sys.stderr)
        return True
    if json_mode:
        emit_error(MelodyctlError(refusal, code="unverified"), True)
    else:
        print(f"error: {refusal} re-run with --force to send anyway.", file=sys.stderr)
    return False


def _anc_label(mode: dict | None) -> str | None:
    if not mode or mode.get("mode_type") is None:
        return None
    return MODE_NAMES.get(mode["mode_type"], f"type{mode['mode_type']}")


def _anc_index(value: str, profile: dict | None) -> int | None:
    """Resolve an 'anc set' argument: a mode name (via MODE_NAMES) or bit:N."""
    v = value.strip().lower()
    if v.startswith("bit:"):
        try:
            return int(v[4:], 0)
        except ValueError:
            return None
    for m in devices.anc_modes(profile):
        if MODE_NAMES.get(m.get("mode_type")) == v and m.get("protocol_index") is not None:
            return m["protocol_index"]
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="melodyctl",
        description="Control HeyMelody-family earbuds (OPPO Enco / OnePlus Buds) "
                    "over the OPOv1/RFCOMM protocol")
    ap.add_argument("-V", "--version", action="version", version=f"melodyctl {__version__}")
    ap.add_argument("-a", "--addr", default=ADDR_DEFAULT, help="buds Bluetooth address")
    ap.add_argument("--channel", type=int,
                    help="RFCOMM channel override (default: probe 12, 15, then 1-30)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_bat = sub.add_parser("battery", help="read Left/Right/Case battery")
    p_bat.add_argument("--json", action="store_true", help="flat {left,right,case} levels (for widgets)")
    p_bat.add_argument("--json-full", action="store_true", help="levels + charging flags")

    p_mon = sub.add_parser("monitor", help="poll battery continuously")
    p_mon.add_argument("-i", "--interval", type=float, default=30.0)
    p_mon.add_argument("--json", action="store_true")

    sub.add_parser("devinfo", help="query device info (raw)")

    p_dev = sub.add_parser("device", help="identify the connected device (product id, whitelist profile, caps)")
    p_dev.add_argument("--json", action="store_true")

    p_rep = sub.add_parser("report", help="read-only compatibility report (safe to paste in an issue)")
    p_rep.add_argument("--with-addr", action="store_true",
                       help="include the Bluetooth address (default: omitted)")

    p_anc = sub.add_parser("anc", help="show noise-cancelling state, or 'anc set <mode>'")
    p_anc.add_argument("action", nargs="?", choices=["set"], help="omit to just show the current mode")
    p_anc.add_argument("mode", nargs="?",
                       help="mode name (off, transparency, nc, deep, smart, ...) or bit:N")
    p_anc.add_argument("--json", action="store_true")
    p_anc.add_argument("-f", "--force", action="store_true",
                       help="send even if the product id is not a verified profile")

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
                      help="which control: 1=tap/touch, 5=middle button")
    p_gs.add_argument("action", nargs="?", type=lambda v: _resolve_int(v, ACTION_ALIASES, "action"),
                      help="which gesture: 1=single ... 4=long press; 16-20=pinch on models that have it")
    p_gs.add_argument("function", nargs="?", type=lambda v: _resolve_int(v, FUNCTION_ALIASES, "function"),
                      help="what it does, e.g. play/pause, prev, next, vol+, assistant, game, none")
    p_gs.add_argument("-f", "--force", action="store_true",
                      help="send even if the device's profile does not allow the combo, "
                           "or the product id is unverified")
    p_gs.add_argument("-l", "--list", action="store_true",
                      help="print the gesture value tables and exit (no device connection)")
    p_gs.add_argument("-p", "--product", type=_product_id, metavar="ID",
                      help="with --list: the whitelist profile to list allowed combos for, "
                           "e.g. 062410 (offline - no device connection)")
    p_gs.add_argument("--json", action="store_true",
                      help="machine-readable output: the vocabulary + slot table with "
                           "--list, or one result object for a write")

    p_fw = sub.add_parser("fw", help="read component versions (buds/case firmware)")
    p_fw.add_argument("--json", action="store_true")
    p_fw.add_argument("--raw", action="store_true")

    p_eqs = sub.add_parser(
        "eq-set", help="select EQ preset by protocol index (other models; experimental)")
    p_eqs.add_argument("index", type=lambda v: int(v, 0))
    p_eqs.add_argument("-f", "--force", action="store_true",
                       help="send even if the product id is not a verified profile")

    p_game = sub.add_parser("game", help="toggle game (low-latency) mode")
    p_game.add_argument("state", choices=["on", "off"])
    p_game.add_argument("-f", "--force", action="store_true",
                        help="send even if the product id is not a verified profile")

    p_watch = sub.add_parser(
        "watch", help="subscribe to device pushes (battery, case/bud status, "
                      "gestures, game mode)")
    p_watch.add_argument("--json", action="store_true",
                         help="one JSON object per event: 'ts' epoch, 'hex' wire "
                              "payload, 'via' the frame that carried it")
    p_watch.add_argument("-e", "--events",
                         help="comma-separated event ids to register, e.g. 1 or 1,2 "
                              "(default: everything the device advertises)")
    p_watch.add_argument("--reconnect", action="store_true",
                         help="wait for the earbuds at startup and reconnect "
                              "whenever they drop (they do when cased/idle)")
    p_watch.add_argument("--retry-max", type=float, default=15.0, metavar="SECONDS",
                         help="cap the reconnect back-off (default 15; a daemon "
                              "watching for hours wants something larger)")
    p_watch.add_argument("-f", "--force", action="store_true",
                         help="register event ids even when the device does not "
                              "advertise them (for probing only - a refusal does "
                              "not prove the id never arrives, but a push that "
                              "does arrive is a lead to capture, not state proof)")

    p_raw = sub.add_parser("raw", help="send a raw hex packet")
    p_raw.add_argument("hex")

    args = ap.parse_args(argv)
    if args.channel is not None:
        os.environ["MELODYCTL_CHANNEL"] = str(args.channel)

    json_mode = "--json" in (sys.argv[1:] if argv is None else argv)

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

        if args.cmd == "device":
            with Buds(args.addr) as conn:
                pid = _identify(conn)
                channel = conn.channel
            profile = devices.profile_for(pid)
            verified = devices.is_verified(pid)
            if args.json:
                print(json.dumps({
                    "id": pid,
                    "name": profile.get("name") if profile else None,
                    "brand": profile.get("brand") if profile else None,
                    "verified": verified,
                    "caps": devices.caps_summary(profile) if profile else None,
                    "channel": channel,
                }))
                return 0 if pid else 1
            if pid is None:
                print("product id : unknown (device did not answer 0x0103)", file=sys.stderr)
                return 1
            print(f"product id : {pid}")
            if profile:
                status = ("verified (this project)" if verified
                          else "untested (whitelist-derived, read-only)")
                print(f"device     : {profile.get('name', '?')} [{profile.get('brand', '?')}]")
                print(f"status     : {status}")
                print(f"caps       : {', '.join(devices.caps_summary(profile)) or '(none known)'}")
            else:
                print("device     : not in the HeyMelody whitelist (unknown id)")
            print(f"channel    : {channel}")
            if not verified:
                print("note       : writes need --force until this device is verified")
            return 0

        if args.cmd == "report":
            def _try(fn):
                try:
                    return fn()
                except Exception as exc:  # noqa: BLE001 - report keeps going
                    return {"error": str(exc)}

            with Buds(args.addr) as conn:
                pid = _try(lambda: _identify(conn))
                if isinstance(pid, dict):
                    pid = None
                caps_resp = _try(lambda: conn.send(CMD_CAPS))
                caps_payload = (caps_resp[0]["payload"]
                                if isinstance(caps_resp, list) and caps_resp else b"")
                advertised = sorted(decode_caps(caps_payload)) if caps_payload else []
                versions = _try(conn.versions)
                battery = _try(conn.battery)
                anc_resp = _try(lambda: conn.send(CMD_ANC_QUERY, b"\x01\x01"))
                anc_payload = (anc_resp[0]["payload"].hex(" ").upper()
                               if isinstance(anc_resp, list) and anc_resp else None)
                transport_info = {"channel": conn.channel,
                                  "discovered": conn.channel_discovered}
            profile = devices.profile_for(pid)
            report = {
                "tool": {"name": "melodyctl", "version": __version__,
                         "date": time.strftime("%Y-%m-%d")},
                "address": args.addr if args.with_addr else "(omitted; re-run with --with-addr)",
                "transport": transport_info,
                "product": {"id": pid,
                            "name": (profile or {}).get("name"),
                            "in_whitelist": profile is not None,
                            "verified": devices.is_verified(pid)},
                "whitelist_caps": devices.caps_summary(profile) if profile else None,
                "caps": {"bitmap": caps_payload.hex(" ").upper() if caps_payload else None,
                         "advertised": [f"0x{c:04x}" for c in advertised]},
                "firmware": versions,
                "battery": battery,
                "anc_query": {"payload": anc_payload,
                              "note": "raw 0x010c reply; type-tagged; no bitmap window on ETI81"},
            }
            print(json.dumps(report, indent=2))
            return 0

        if args.cmd == "anc":
            if args.action == "set" and not args.mode:
                print("anc set: missing mode; run 'melodyctl anc' to list this device's modes",
                      file=sys.stderr)
                return 2
            with Buds(args.addr) as conn:
                pid = _identify(conn)
                profile = devices.profile_for(pid)
                if args.action == "set":
                    if not _write_gate(pid, "anc", args.force):
                        return 2
                    table = devices.anc_modes(profile)
                    if profile is not None and not table:
                        print(f"error: {profile.get('name', pid)} has no ANC in its whitelist "
                              f"entry (no noiseReductionMode); there is nothing to switch.",
                              file=sys.stderr)
                        return 2
                    idx = _anc_index(args.mode, profile)
                    if idx is None:
                        print(f"error: unknown ANC mode {args.mode!r} for this device; "
                              f"run 'melodyctl anc' to list the whitelist modes.", file=sys.stderr)
                        return 2
                    bitmap = anc_bitmap(idx)
                    resp = conn.anc_set(bitmap)
                    ack = resp[0]["payload"][0] if resp and resp[0]["payload"] else None
                    time.sleep(1.0)
                    q = conn.anc_query()
                    qp = q[0]["payload"] if q else b""
                    active = decode_anc_bitmap(qp[2:]) if qp[:2] == b"\x01\x01" else None
                    print(f"anc set {args.mode} -> bit {idx}, bitmap "
                          f"{bitmap.hex(' ').upper()}, ack {ack}")
                    print(f"read-back: {('bit ' + str(active)) if active is not None else 'no bitmap'}"
                          f" ({'ok' if active == idx else 'NOT confirmed'})")
                    return 0 if active == idx else 1
                resp = conn.anc_query()
                payload = resp[0]["payload"] if resp else b""
                active = None
                mode = None
                if payload[:2] == b"\x01\x01":
                    active = decode_anc_bitmap(payload[2:])
                    mode = (devices.anc_mode_for_bit(profile, active)
                            if active is not None else None)
                modes = [{"name": _anc_label(m), "bit": m.get("protocol_index"),
                          "mode_type": m.get("mode_type")}
                         for m in devices.anc_modes(profile)]
                if args.json:
                    print(json.dumps({"product_id": pid,
                                      "raw": payload.hex(" ").upper() or None,
                                      "active_bit": active,
                                      "active_mode": _anc_label(mode),
                                      "modes": modes}))
                    return 0
                if not payload:
                    print("no response to 0x010c", file=sys.stderr)
                    return 1
                print(f"raw reply : {payload.hex(' ').upper()}")
                if payload == b"\x02":
                    print("state     : no noise-mode info (bare 02 type reply, no bitmap)")
                    if profile is not None and not modes:
                        print("note      : this device has no ANC in its whitelist entry")
                elif active is not None:
                    print(f"active    : {_anc_label(mode) or 'unknown'} (bit {active})")
                if modes:
                    print("modes     : " + ", ".join(
                        f"{m['name']}@{m['bit']}" for m in modes if m["name"]))
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
            return 0

        if args.cmd == "gestures":
            with Buds(args.addr) as conn:
                pid = _identify(conn)
                profile = devices.profile_for(pid)
                g = conn.gestures(devices.oneplus_branch(profile))
            if args.json:
                print(json.dumps(g))
            else:
                for r in g:
                    btn = "" if r["button"] == 1 else f" [{r['button_name']}]"
                    print(f"{r['ear']:<5} {r['action_name']:<18}{btn} -> "
                          f"{r['function_name']:<28} (f{r['function']})")
            return 0

        if args.cmd == "gesture-set":
            if args.list:
                if not args.json:
                    print(_gesture_tables())
                    return 0
                profile = None
                if args.product:
                    profile = devices.profile_for(args.product)
                    if profile is None:
                        emit_error(MelodyctlError(
                            f"product id {args.product} is not in the HeyMelody "
                            f"whitelist, so there is no slot table to list",
                            code="unknown_device"), True)
                        return 2
                print(json.dumps(_gesture_json(profile, args.product)))
                return 0
            missing = [n for n, v in (("ear", args.ear), ("button", args.button),
                                      ("action", args.action), ("function", args.function))
                       if v is None]
            if missing:
                if args.json:
                    emit_error(MelodyctlError(
                        f"missing {'/'.join(missing)}", code="usage"), True)
                else:
                    print(f"gesture-set: missing {'/'.join(missing)}; "
                          f"run 'melodyctl gesture-set --list' to see values", file=sys.stderr)
                return 2
            if args.ear not in EAR:
                if args.json:
                    emit_error(MelodyctlError(
                        f"ear {args.ear} is not 1=left/2=right/4=both", code="usage"), True)
                else:
                    print(f"error: ear {args.ear} is not 1=left/2=right/4=both",
                          file=sys.stderr)
                return 2

            with Buds(args.addr) as conn:
                pid = _identify(conn)
                profile = devices.profile_for(pid)
                problems = _gesture_write_problems(profile, args)
                if problems and not args.force:
                    if args.json:
                        emit_error(MelodyctlError("; ".join(problems), code="profile"), True)
                    else:
                        for p in problems:
                            print(f"error: {p}", file=sys.stderr)
                        print("       re-run with --force to send anyway.", file=sys.stderr)
                    return 2
                for p in problems:
                    if not args.json:
                        print(f"warning: {p} (sending anyway due to --force)", file=sys.stderr)
                if not _write_gate(pid, "gesture", args.force, args.json):
                    return 2
                resp = conn.set_gesture(args.ear, args.button, args.action, args.function)
            if not resp:
                emit_error(MelodyctlError("no ack (command unsupported or rejected)",
                                          code="no_ack"), args.json)
                return 1
            acks = [r["payload"][0] if r["payload"] else None for r in resp]
            ok = bool(acks) and all(a == 0 for a in acks)
            op = devices.oneplus_branch(profile)
            fn = function_name(args.function, op)
            if args.json:
                print(json.dumps({
                    "ok": ok,
                    "acks": acks,
                    "ear": {"id": args.ear, "name": EAR.get(args.ear, str(args.ear))},
                    "button": {"id": args.button, "name": BUTTON_NAMES.get(args.button)},
                    "action": {"id": args.action, "name": ACTION_NAMES.get(args.action)},
                    "function": {"id": args.function, "name": fn},
                }))
            else:
                print(f"set ear={EAR.get(args.ear, args.ear)} button={BUTTON_NAMES.get(args.button, args.button)} "
                      f"action={ACTION_NAMES.get(args.action, args.action)} "
                      f"function={fn} -> ack {acks} ({'ok' if ok else 'rejected'})")
            return 0 if ok else 1

        if args.cmd == "fw":
            with Buds(args.addr) as conn:
                frames = conn.send(CMD_VERSION_GET)
            if not frames:
                print("no version response", file=sys.stderr)
                return 1
            payload = frames[0]["payload"]
            if args.raw:
                print(payload.hex(" ").upper())
                return 0
            records = decode_version_records(payload)
            if args.json:
                print(json.dumps(records))
            else:
                print(_fmt_versions(records))
            return 0

        if args.cmd == "eq-set":
            with Buds(args.addr) as conn:
                if not _write_gate(_identify(conn), "eq preset", args.force):
                    return 2
                resp = conn.set_eq(args.index)
            print(f"set EQ index={args.index} -> " +
                  (", ".join(f"0x{f['cmd']:04x}:{f['payload'].hex(' ').upper()}" for f in resp) or "no ack"))
            return 0 if resp else 1

        if args.cmd == "game":
            with Buds(args.addr) as conn:
                if not _write_gate(_identify(conn), "game-mode", args.force):
                    return 2
                resp = conn.set_game_mode(args.state == "on")
            code = resp[0]["payload"][0] if resp and resp[0]["payload"] else None
            print(f"game mode {args.state} -> ack {code} "
                  f"({'ok' if code == 0 else 'rejected'})")
            return 0 if code == 0 else 1

        if args.cmd == "watch":
            with _session(args.addr, args.reconnect, args.retry_max) as conn:
                pid = _identify(conn)
                profile = devices.profile_for(pid)
                op = devices.oneplus_branch(profile)
                advertised = conn.notify_caps()
                # The app registers with one 0x0205 when the device advertises
                # that command, else one 0x0201 per id [apk:j#c].
                bulk = CMD_NOTIFY_REG_MULTI in conn.caps()
                wanted = advertised
                if args.events:
                    try:
                        wanted = [int(x, 0) for x in args.events.replace(",", " ").split()]
                    except ValueError:
                        print(f"error: --events takes event ids like 1 or 1,2 - "
                              f"got {args.events!r}", file=sys.stderr)
                        return 2
                    skipped = [e for e in wanted if e not in advertised]
                    if skipped and not args.force:
                        # subscribe only to what the device advertises
                        print("warning: device does not advertise event "
                              + ", ".join(str(e) for e in skipped)
                              + "; not registering those", file=sys.stderr)
                        wanted = [e for e in wanted if e in advertised]
                    elif skipped:
                        _watch_info("warning: registering event "
                                    + ", ".join(str(e) for e in skipped)
                                    + " though the device does not advertise it - "
                                    "probing only, not state proof", args.json)
                _watch_info("pushable events: " + (", ".join(
                    f"{e}({NOTIFY_NAMES.get(e, '?')})" for e in advertised)
                    or "(none)"), args.json)
                if not wanted:
                    print("nothing to watch: no advertised event id matched",
                          file=sys.stderr)
                    return 1
                reg = conn.register_notify(wanted, bulk=bulk)
                acks = reg["acks"]
                rejected = [e for e, a in acks.items() if a]
                note = ""
                if reg["bulk_attempted"] and reg["style"] == "per-event":
                    note = " (0x0205 not accepted, fell back)"
                _watch_info(f"registered {len(wanted)} event(s) via {reg['style']}{note}"
                            + (f"; rejected: {rejected}" if rejected else ""),
                            args.json)
                _watch_info("watching for pushes - open/close the case, take the "
                            "buds out, tap them. Ctrl-C to stop.", args.json)
                while True:
                    try:
                        for ev in conn.iter_events(1.0, op, pid):
                            _watch_line(ev, args.json)
                        return 0         # only on a clean stop
                    except MelodyctlError as exc:
                        # The buds close the link when they idle or are cased;
                        # the socket never revives, so a new one is required.
                        if not args.reconnect or exc.code != "disconnected":
                            raise
                        _watch_info(f"  [{time.strftime('%H:%M:%S')}] {exc}", args.json)
                        _watch_info("  waiting for the earbuds (Ctrl-C to stop)...",
                                    args.json)
                        delay = 2.0
                        attempt = 0
                        while True:
                            attempt += 1
                            time.sleep(delay)
                            try:
                                conn.reconnect(wanted, bulk=bulk)
                            except Exception as exc2:  # noqa: BLE001
                                _retry_log(attempt, exc2, delay)
                                delay = min(delay * 2, args.retry_max)
                                continue
                            _watch_info("  reconnected - watching again.", args.json)
                            break
            return 0

        if args.cmd == "raw":
            with Buds(args.addr) as conn:
                print(conn.raw(bytes.fromhex(args.hex.replace(" ", ""))).hex(" ").upper())
            return 0
    except KeyboardInterrupt:
        # Ctrl-C: exit quietly (no traceback) with the conventional 130.
        return 130
    except Exception as exc:  # noqa: BLE001 - users get one clean line, never a traceback
        emit_error(exc, json_mode)
        if os.environ.get("MELODYCTL_DEBUG") == "1":
            traceback.print_exc()
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
