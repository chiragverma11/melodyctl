#!/usr/bin/env python3
"""Enumerate GATT services/characteristics of the OPPO Enco Buds."""
import asyncio
import sys

from bleak import BleakClient, BleakScanner

ADDR = "6C:0D:E1:5F:DB:4D"


async def main() -> None:
    print(f"[*] Scanning for {ADDR} ...")
    dev = await BleakScanner.find_device_by_address(ADDR, timeout=20.0)
    if dev is None:
        print("[!] Not found by address; dumping nearby devices:")
        for d in await BleakScanner.discover(timeout=10.0):
            print(f"    {d.address}  {d.name}")
        sys.exit(1)

    print(f"[+] Found {dev.address}  name={dev.name}")
    async with BleakClient(dev.address, timeout=30.0) as client:
        print(f"[+] Connected: {client.is_connected}")
        for svc in client.services:
            print(f"\nSERVICE {svc.uuid}  ({svc.description})")
            for ch in svc.characteristics:
                print(f"  CHAR {ch.uuid}  props={','.join(ch.properties)}")
                for d in ch.descriptors:
                    print(f"    DESC {d.uuid}")


if __name__ == "__main__":
    asyncio.run(main())
