"""API del Kitchen Smart Display: REST + WebSocket sobre módulos asíncronos."""

from __future__ import annotations

import asyncio
import logging
import os
import socket
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from .config import MISSING_ENV, AppConfig, get_config
from .modules.adguard import AdguardModule
from .modules.base import PollingModule
from .modules.calendar import CalendarModule
from .modules.keep import KeepModule
from .modules.nas import NasModule
from .modules.news import NewsModule
from .modules.sems import SemsModule
from .modules.solar import SolarModule
from .modules.spotify import SpotifyModule
from .modules.weather import WeatherModule
from .schemas.models import (
    AdguardStats,
    CalendarData,
    HealthResponse,
    ModuleData,
    NasStatus,
    NewsData,
    NowPlaying,
    ShoppingList,
    SolarData,
    WeatherData,
    WeatherLocationInfo,
)

log = logging.getLogger("dashboard")

PORT_BUSY_EXIT_DELAY_SECONDS = 30


class SolarBroadcaster:
    """Difunde cada lectura del inversor a los clientes de ``/ws/solar``."""

    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()

    def add(self, ws: WebSocket) -> None:
        self._clients.add(ws)

    def remove(self, ws: WebSocket) -> None:
        self._clients.discard(ws)

    async def _send(self, ws: WebSocket, payload: str) -> None:
        try:
            await asyncio.wait_for(ws.send_text(payload), timeout=5)
        except Exception:  # noqa: BLE001 - cliente caído o lento
            self.remove(ws)

    async def broadcast(self, data: ModuleData) -> None:
        if self._clients:
            payload = data.model_dump_json()
            await asyncio.gather(*(self._send(ws, payload) for ws in list(self._clients)))


def build_modules(cfg: AppConfig, client: httpx.AsyncClient) -> dict[str, PollingModule]:
    tz = cfg.server.tz
    modules: dict[str, PollingModule] = {}
    sems = SemsModule(cfg.sems, client, tz) if cfg.sems and cfg.sems.enabled else None
    if sems is not None:
        modules["sems"] = sems
    inverter = cfg.inverter if cfg.inverter and cfg.inverter.enabled else None
    if inverter is not None or sems is not None:
        modules["solar"] = SolarModule(inverter, sems, tz)
    if cfg.calendars and cfg.calendars.enabled:
        modules["calendar"] = CalendarModule(cfg.calendars, client, tz)
    if cfg.weather and cfg.weather.enabled:
        for index, location in enumerate(cfg.weather.locations):
            modules[f"weather:{index}"] = WeatherModule(location, cfg.weather.update_interval_minutes, client)
    if cfg.keep and cfg.keep.enabled:
        modules["keep"] = KeepModule(cfg.keep)
    if cfg.omv and cfg.omv.enabled:
        modules["nas"] = NasModule(cfg.omv)
    if cfg.adguard and cfg.adguard.enabled:
        modules["adguard"] = AdguardModule(cfg.adguard, client)
    if cfg.spotify and cfg.spotify.enabled:
        modules["spotify"] = SpotifyModule(cfg.spotify, client)
    if cfg.news and cfg.news.enabled:
        modules["news"] = NewsModule(cfg.news, client)
    return modules


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    cfg = get_config()
    client = httpx.AsyncClient(
        timeout=httpx.Timeout(15.0, connect=5.0),
        headers={"User-Agent": "KitchenDashboard/1.0"},
    )
    modules = build_modules(cfg, client)
    broadcaster = SolarBroadcaster()
    if "solar" in modules:
        modules["solar"].subscribe(broadcaster.broadcast)

    app.state.modules = modules
    app.state.broadcaster = broadcaster
    for module in modules.values():
        module.start()
    log.info("Módulos activos: %s", ", ".join(modules) or "ninguno")
    if MISSING_ENV:
        log.warning("Variables de entorno usadas en config.yaml sin definir: %s", ", ".join(sorted(MISSING_ENV)))
    try:
        yield
    finally:
        await asyncio.gather(*(m.stop() for m in modules.values()), return_exceptions=True)
        await client.aclose()


app = FastAPI(title="Kitchen Smart Display", version="1.0.0", lifespan=lifespan)


def _module(request: Request, name: str) -> PollingModule:
    module = request.app.state.modules.get(name)
    if module is None:
        raise HTTPException(status_code=404, detail=f"Módulo '{name}' deshabilitado")
    return module


def _serve(request: Request, name: str) -> ModuleData:
    data = _module(request, name).snapshot()
    if data is None:
        raise HTTPException(status_code=503, detail=f"Módulo '{name}' sin datos todavía")
    return data


@app.get("/api/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    return HealthResponse(modules={name: m.health() for name, m in request.app.state.modules.items()})


@app.get("/api/solar/current", response_model=SolarData)
async def solar_current(request: Request) -> ModuleData:
    return _serve(request, "solar")


@app.get("/api/calendar", response_model=CalendarData)
async def calendar(request: Request) -> ModuleData:
    return _serve(request, "calendar")


@app.get("/api/weather/locations", response_model=list[WeatherLocationInfo])
async def weather_locations(request: Request) -> list[WeatherLocationInfo]:
    """Ubicaciones configuradas; la de índice 0 es la principal."""
    return [
        WeatherLocationInfo(index=int(key.split(":", 1)[1]), name=module.location.name)
        for key, module in request.app.state.modules.items()
        if key.startswith("weather:")
    ]


@app.get("/api/weather", response_model=WeatherData)
async def weather(request: Request) -> ModuleData:
    return _serve(request, "weather:0")


@app.get("/api/weather/{index}", response_model=WeatherData)
async def weather_at(request: Request, index: int) -> ModuleData:
    return _serve(request, f"weather:{index}")


@app.get("/api/keep/shopping-list", response_model=ShoppingList)
async def shopping_list(request: Request) -> ModuleData:
    return _serve(request, "keep")


@app.get("/api/system/nas", response_model=NasStatus)
async def nas(request: Request) -> ModuleData:
    return _serve(request, "nas")


@app.get("/api/network/adguard", response_model=AdguardStats)
async def adguard(request: Request) -> ModuleData:
    return _serve(request, "adguard")


@app.get("/api/media/now-playing", response_model=NowPlaying)
async def now_playing(request: Request) -> ModuleData:
    return _serve(request, "spotify")


@app.get("/api/news", response_model=NewsData)
async def news(request: Request) -> ModuleData:
    return _serve(request, "news")


@app.websocket("/ws/solar")
async def solar_ws(ws: WebSocket) -> None:
    await ws.accept()
    module: PollingModule | None = ws.app.state.modules.get("solar")
    if module is None:
        await ws.close(code=1008, reason="Módulo solar deshabilitado")
        return

    broadcaster: SolarBroadcaster = ws.app.state.broadcaster
    broadcaster.add(ws)
    try:
        if (snapshot := module.snapshot()) is not None:
            await ws.send_text(snapshot.model_dump_json())
        while True:
            await ws.receive_text()  # pings de keep-alive del cliente; se ignoran
    except WebSocketDisconnect:
        pass
    finally:
        broadcaster.remove(ws)


# ── Frontend (SPA compilada) ─────────────────────────────────────────────────
# Se registra al final para que las rutas de la API tengan prioridad.

STATIC_DIR = Path(os.environ.get("STATIC_DIR", "/app/static"))


@app.get("/{path:path}", include_in_schema=False)
async def spa(path: str) -> Response:
    if path == "api" or path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Ruta no encontrada")

    root = STATIC_DIR.resolve()
    index = root / "index.html"
    if not index.is_file():
        raise HTTPException(status_code=404, detail="Frontend no compilado")

    candidate = (root / path).resolve()
    if path and candidate.is_file() and candidate.is_relative_to(root):
        # Los ficheros de assets/ llevan hash en el nombre: caché permanente.
        cache = "public, max-age=31536000, immutable" if path.startswith("assets/") else "no-cache"
        return FileResponse(candidate, headers={"Cache-Control": cache})
    # index.html sin caché para que el kiosko recoja siempre la última build.
    return FileResponse(index, headers={"Cache-Control": "no-store"})


def main() -> None:
    cfg = get_config()
    logging.basicConfig(
        level=cfg.server.log_level.upper(),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    for noisy in ("httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    # El puerto se reserva antes de arrancar los módulos: si está ocupado, uvicorn
    # fallaría después de iniciarlos y cada reinicio del contenedor repetiría los
    # logins (Keep, SEMS...).
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind((cfg.server.host, cfg.server.port))
    except OSError as exc:
        log.error(
            "No se puede escuchar en %s:%s (%s). Otro servicio usa ese puerto: cambia server.port en config.yaml.",
            cfg.server.host, cfg.server.port, exc.strerror,
        )
        time.sleep(PORT_BUSY_EXIT_DELAY_SECONDS)  # frena el bucle de reinicios de Docker
        raise SystemExit(1) from exc

    config = uvicorn.Config(app, proxy_headers=True, access_log=False, log_level=cfg.server.log_level.lower())
    uvicorn.Server(config).run(sockets=[sock])


if __name__ == "__main__":
    main()
