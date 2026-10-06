#!/usr/bin/env python3
"""Identifica qué IP es el inversor GoodWe y qué datos expone.

Uso (desde la raíz del proyecto, en una máquina de la LAN sin VPN, p. ej. el NAS):

    docker compose run --rm -v "$PWD/scripts:/scripts:ro" dashboard \\
        python /scripts/goodwe_probe.py [IP ...]

Sin IPs, busca los dispositivos GoodWe de la red por broadcast.
"""

from __future__ import annotations

import asyncio
import sys

import goodwe

# Sensores que usa el dashboard (backend/app/modules/solar.py).
INTERESTING = ("ppv", "house_consumption", "active_power", "pbattery1", "battery_soc", "e_day", "e_total", "meter_active_power")


async def discover() -> list[str]:
    raw = await goodwe.search_inverters()
    ips = []
    for line in raw.decode(errors="replace").split("\x00"):
        parts = line.strip().split(",")
        if len(parts) >= 3:
            print(f"Encontrado: {parts[0]}  MAC {parts[1]}  {parts[2]}")
            ips.append(parts[0])
    return ips


async def probe(ip: str) -> None:
    try:
        inverter = await goodwe.connect(host=ip, timeout=2, retries=3)
    except Exception as exc:  # noqa: BLE001
        print(f"\n{ip}: no responde como inversor ({type(exc).__name__}). Probablemente sea el HomeKit.")
        return

    data = await inverter.read_runtime_data()
    print(f"\n{ip}: INVERSOR {inverter.model_name} (familia {type(inverter).__name__}, S/N {inverter.serial_number})")
    for key in INTERESTING:
        if key in data:
            print(f"   {key:20} = {data[key]}")
    missing = [k for k in ("house_consumption", "active_power") if k not in data]
    if missing:
        print(f"   ⚠ No expone {', '.join(missing)}: el consumo/red se mediría solo con el HomeKit.")


async def main() -> None:
    ips = sys.argv[1:] or await discover()
    if not ips:
        sys.exit("No se encontró ningún dispositivo GoodWe (¿VPN activa o red distinta?).")
    for ip in ips:
        await probe(ip)


if __name__ == "__main__":
    asyncio.run(main())
