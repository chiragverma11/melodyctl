"""Command-line interface: argparse surface, command handlers, output formatting."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback

from . import __version__, devices
from .errors import emit_error
from .protocol import ACTION_ALIASES, ACTION_FUNCTIONS, ACTION_NAMES, BUTTON_ALIASES, BUTTON_NAMES, CMD_ANC_QUERY, CMD_BATT_GET, CMD_CAPS, CMD_EQ_SET, CMD_GAMESOUND_SET, CMD_GESTURES_GET, CMD_GESTURES_SET, CMD_INFO, CMD_NOTIFY_PUSH, CMD_SWITCH_FEATURE, CMD_VERSION_GET, EAR, EAR_ALIASES, FUNCTION_ALIASES, FUNCTION_NAMES, NOTIFY_NAMES, NOTIFY_USER_INTERACTION, _fmt_battery, _fmt_versions, decode_caps, decode_product_id, decode_user_interaction, decode_version_records, parse_frames
from .transport import ADDR_DEFAULT, Buds


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


def _identify(conn: Buds) -> str | None:
    """Product id from 0x0103 ('062410'), or None when the device stays silent."""
    resp = conn.send(CMD_INFO)
    return decode_product_id(resp[0]["payload"]) if resp else None


def _write_gate(pid: str | None, action: str, force: bool) -> bool:
    """Enforce the write gate: verified profiles only. False = refused (printed)."""
    refusal = devices.write_refusal(pid, action)
    if refusal is None:
        return True
    if force:
        print(f"warning: {refusal} sending anyway (--force)", file=sys.stderr)
        return True
    print(f"error: {refusal} re-run with --force to send anyway.", file=sys.stderr)
    return False


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="melodyctl", description="OPPO Enco Buds control (OPOv1/RFCOMM)")
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
                      help="send even if the combo is not advertised or the product id is unverified")
    p_gs.add_argument("-l", "--list", action="store_true",
                      help="print the gesture value tables and exit (no device connection)")

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

    sub.add_parser("watch", help="subscribe to device events (tap the buds to map gestures)")

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
                              "note": "raw 0x010c reply; not interpreted (OQ-1)"},
            }
            print(json.dumps(report, indent=2))
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
                if not _write_gate(_identify(conn), "gesture", args.force):
                    return 2
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
