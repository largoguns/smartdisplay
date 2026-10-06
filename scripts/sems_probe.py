#!/usr/bin/env python3
"""Comprueba el acceso a SEMS+ (nube de GoodWe) y muestra el flujo de energía
de la planta: producción, consumo del hogar y red (medidos por el HomeKit).

Uso (solo librería estándar; la contraseña se pide oculta y no se guarda):

    python3 scripts/sems_probe.py <email_sems> <station_id>
"""

from __future__ import annotations

import base64
import getpass
import hashlib
import json
import sys
import time
import urllib.request

GATEWAY = "https://eu-gateway.semsportal.com/web/sems"


def signature(token: dict) -> str:
    # Igual que la web de SEMS+: base64(sha256("ts@uid@token") + "@ts")
    ts = str(int(time.time() * 1000))
    digest = hashlib.sha256(f"{ts}@{token.get('uid', '')}@{token.get('token', '')}".encode()).hexdigest()
    return base64.b64encode(f"{digest}@{ts}".encode()).decode()


def request(method: str, url: str, token: dict, body: dict | None = None) -> dict:
    headers = {
        "Content-Type": "application/json",
        "token": json.dumps(token),
        "x-signature": signature(token) if token.get("token") else "",
        "currentlang": "es",
    }
    data = json.dumps(body).encode() if body is not None else None
    with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers, method=method), timeout=20) as r:
        return json.load(r)


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    email, station_id = sys.argv[1], sys.argv[2]
    password = getpass.getpass("Contraseña de SEMS (no se muestra): ")

    anonymous = {"uid": "", "timestamp": 0, "token": "", "client": "semsPlusWeb", "version": "", "language": "es"}
    login = request(
        "POST",
        f"{GATEWAY}/sems-user/api/v1/auth/cross-login",
        anonymous,
        {
            "account": email,
            "pwd": base64.b64encode(hashlib.md5(password.encode()).hexdigest().encode()).decode(),
            "agreement": 1,
            "isLocal": False,
            "isChinese": False,
        },
    )
    if login.get("code") not in ("00000", "0", 0) or not login.get("data"):
        sys.exit(f"Login rechazado: {login.get('code')} {login.get('description') or login.get('errorMsg')}")
    data = login["data"]
    # Solo los nombres de los campos: nada sensible.
    print("Login correcto. Campos de la sesión:", sorted(data))
    if data.get("mfaRequired"):
        sys.exit("La cuenta tiene verificación en dos pasos: no se puede automatizar el login.")

    token = {k: data.get(k, "") for k in ("uid", "timestamp", "token")} | {"client": "semsPlusWeb", "version": "", "language": "es"}
    api = data.get("api") or GATEWAY
    flow = request("GET", f"{api}/sems-plant/api/stations/flow?stationId={station_id}", token)
    print(f"api: {api}")
    print(json.dumps(flow.get("data"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
