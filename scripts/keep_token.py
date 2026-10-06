#!/usr/bin/env python3
"""Obtiene el master token de Google ("aas_et/...") para la lista de Google Keep.

1. Abre https://accounts.google.com/EmbeddedSetup en el navegador e inicia
   sesión con la cuenta que tiene la lista "La Compra". Acepta las
   condiciones ("Acepto"); es normal que después la página se quede cargando.
2. DevTools (F12) → Application → Cookies → https://accounts.google.com →
   copia el valor de la cookie ``oauth_token`` (empieza por "oauth2_4/").
   Caduca en pocos minutos: ejecuta este script enseguida.
3. Desde la raíz del proyecto:

   docker compose run --rm -it -v "$PWD/scripts:/scripts:ro" backend python /scripts/keep_token.py

Necesita ``gpsoauth`` (incluido en la imagen del backend como dependencia de gkeepapi).
"""

from __future__ import annotations

import getpass
import secrets

import gpsoauth


def main() -> None:
    email = input("Email de Google: ").strip()
    oauth_token = getpass.getpass("Cookie oauth_token (no se muestra): ").strip()
    android_id = secrets.token_hex(8)

    response = gpsoauth.exchange_token(email, oauth_token, android_id)
    token = response.get("Token")
    if not token:
        raise SystemExit(f"Google rechazó el intercambio: {response.get('Error', response)}")
    print(f"\nmaster_token: {token}\n\nCópialo en config.yaml → keep.master_token")


if __name__ == "__main__":
    main()
