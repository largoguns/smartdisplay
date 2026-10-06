#!/usr/bin/env python3
"""Obtiene el refresh token de una cuenta de Spotify para config.yaml.

1. En https://developer.spotify.com/dashboard crea una app y añade como
   Redirect URI exactamente: http://127.0.0.1:8888/callback
   (o el puerto que pases con --port, si el 8888 está ocupado)
2. Ejecuta: python3 scripts/spotify_auth.py <client_id> <client_secret> [--port 8889]
3. Inicia sesión con la cuenta deseada en el navegador. Repite por cuenta
   (usa una ventana privada para cambiar de cuenta) y añade cada cuenta en
   la app como usuario de prueba si está en "Development mode".

Solo usa la librería estándar.
"""

from __future__ import annotations

import argparse
import base64
import http.server
import json
import secrets
import sys
import urllib.parse
import urllib.request
import webbrowser

SCOPES = "user-read-playback-state user-read-currently-playing"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("client_id")
    parser.add_argument("client_secret")
    parser.add_argument("--port", type=int, default=8888, help="puerto local del callback (por defecto 8888)")
    args = parser.parse_args()
    client_id, client_secret = args.client_id, args.client_secret
    redirect_uri = f"http://127.0.0.1:{args.port}/callback"
    state = secrets.token_urlsafe(16)
    result: dict[str, str] = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if query.get("state", [""])[0] == state and "code" in query:
                result["code"] = query["code"][0]
                message = "Listo. Puedes cerrar esta pestaña."
            else:
                result["error"] = query.get("error", ["respuesta no válida"])[0]
                message = f"Error: {result['error']}"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(message.encode())

        def log_message(self, *args: object) -> None:
            pass

    auth_url = "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode(
        {
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "scope": SCOPES,
            "state": state,
            "show_dialog": "true",
        }
    )
    print(f"Abre esta URL si el navegador no se abre solo:\n\n{auth_url}\n")
    try:
        webbrowser.open(auth_url)
    except Exception:  # noqa: BLE001 - en WSL puede no haber navegador; basta con la URL impresa
        pass

    try:
        # Con hilos: los navegadores abren conexiones especulativas vacías que
        # bloquearían a un servidor que atiende de una en una.
        server = http.server.ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
        server.daemon_threads = True
    except OSError:
        sys.exit(f"El puerto {args.port} está ocupado. Usa --port con otro libre y añade su Redirect URI en Spotify.")
    with server:
        server.timeout = 0.5
        while not result:
            server.handle_request()
    if "error" in result:
        sys.exit(f"Autorización fallida: {result['error']}")

    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    request = urllib.request.Request(
        "https://accounts.spotify.com/api/token",
        data=urllib.parse.urlencode(
            {"grant_type": "authorization_code", "code": result["code"], "redirect_uri": redirect_uri}
        ).encode(),
        headers={"Authorization": f"Basic {basic}", "Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(request) as response:
        tokens = json.load(response)
    print("refresh_token:", tokens["refresh_token"])


if __name__ == "__main__":
    main()
