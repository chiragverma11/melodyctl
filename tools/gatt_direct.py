#!/usr/bin/env python3
"""Connect directly to an earbud's LE address and enumerate GATT."""
import asyncio
import sys

from bleak import BleakClient

ADDR = "6C:0D:E1:5F:DB:4D"


async def main() -> None:
    print(f"[*] Direct-connecting to {ADDR} ...")
    try:
        async with BleakClient(ADDR, timeout=30.0) as client:
            print(f"[+] Connected: {client.is_connected}")
            svcs = client.services
            for svc in svcs:
                print(f"\nSERVICE {svc.uuid}  ({svc.description})")
                for ch in svc.characteristics:
                    print(f"  CHAR {ch.uuid}  props={','.join(ch.properties)}")
                    for d in ch.descriptors:
                        print(f"    DESC {d.uuid}")
    except Exception as exc:  # noqa: BLE001
        print(f"[!] {type(exc).__name__}: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
