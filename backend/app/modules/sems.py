"""Flujo de energía desde SEMS+ (nube de GoodWe).

Complementa al inversor local cuando éste no tiene medidor: el consumo del
hogar y el intercambio con la red los mide el HomeKit, que solo los publica en
SEMS. API no oficial, la misma que usa la web semsplus.goodwe.com.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import time
from collections import defaultdict
from datetime import date, datetime, time as dtime
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from ..config import SemsConfig
from ..schemas.models import SemsFlow, SolarDay, SolarDayPoint
from .base import CredentialsError, PollingModule, require_secret, utcnow

OK_CODES = ("00000", "0", 0)
# Sesión caducada o inválida: hay que repetir el login.
AUTH_ERROR_CODES = ("C0602", "C0607", "A0301", "100002", 100002)
CLIENT = "semsPlusWeb"
# Totales del día que muestra la app de SEMS+ (kWh).
DAY_KPIS = ("proSystemTotalStats", "proConsumStats", "proPurchaseStats", "proGridStats")
# Series de la curva de potencia (kW, un punto por minuto).
CURVE_ITEMS = ("pSystem", "pConsum")
CURVE_STEP_MINUTES = 5


class SemsError(Exception):
    def __init__(self, code: Any, message: str) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code


def sign(uid: str, token: str, ts_ms: int | None = None) -> str:
    """Cabecera ``x-signature``: base64(sha256("ts@uid@token") + "@ts")."""
    ts = str(ts_ms if ts_ms is not None else int(time.time() * 1000))
    digest = hashlib.sha256(f"{ts}@{uid}@{token}".encode()).hexdigest()
    return base64.b64encode(f"{digest}@{ts}".encode()).decode()


def hash_password(password: str) -> str:
    return base64.b64encode(hashlib.md5(password.encode()).hexdigest().encode()).decode()


def parse_flow(data: dict[str, Any], tz: ZoneInfo) -> SemsFlow:
    """``flows`` es un grafo origen → destinos; el sentido de la red sale de ahí:
    {"pSystem": ["pConsum", "pGrid"]} = exportando, {"pGrid": [...]} = importando.
    ``pGrid`` ya viene con signo (negativo al importar), así que solo se usa su
    magnitud; el signo decide si ``flows`` no indica sentido."""
    flows: dict[str, list[str]] = data.get("flows") or {}
    grid_kw = float(data.get("pGrid") or 0.0)
    if flows.get("pGrid"):
        grid_w = -abs(grid_kw) * 1000
    elif any("pGrid" in targets for targets in flows.values()):
        grid_w = abs(grid_kw) * 1000
    else:
        grid_w = grid_kw * 1000

    refreshed = data.get("refreshTime")
    return SemsFlow(
        fetched_at=utcnow(),
        pv_w=round(float(data.get("pSystem") or 0.0) * 1000, 1),
        house_w=round(float(data.get("pConsum") or 0.0) * 1000, 1),
        grid_w=round(grid_w, 1),
        refreshed_at=datetime.fromisoformat(refreshed).replace(tzinfo=tz) if refreshed else None,
    )


def _kwh(production: dict[str, Any], key: str) -> float | None:
    value = production.get(key)
    return round(float(value), 2) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def parse_day(day: date, production: dict[str, Any], curve: dict[str, Any]) -> SolarDay:
    """Totales de ``stations/production`` y curva de ``statisticsAndPreV2``,
    promediada en tramos de ``CURVE_STEP_MINUTES`` para aligerar la respuesta."""
    buckets: dict[int, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for series in curve.get("dataList") or []:
        item = series.get("item")
        if item not in CURVE_ITEMS:
            continue
        for point in series.get("powerData") or []:
            power = point.get("power")
            tp = point.get("tp") or ""
            if not isinstance(power, (int, float)) or not tp.startswith(day.isoformat()):
                continue
            moment = datetime.fromisoformat(tp)
            minute = moment.hour * 60 + moment.minute
            buckets[minute - minute % CURVE_STEP_MINUTES][item].append(float(power))

    def avg_w(values: list[float]) -> float:
        # Pequeños negativos de la FV por la noche (autoconsumo del inversor) = 0.
        return round(max(0.0, sum(values) / len(values)) * 1000, 1) if values else 0.0

    points = [
        SolarDayPoint(minute=minute, pv_w=avg_w(series["pSystem"]), house_w=avg_w(series["pConsum"]))
        for minute, series in sorted(buckets.items())
    ]
    return SolarDay(
        fetched_at=utcnow(),
        day=day,
        generated_kwh=_kwh(production, "proSystemTotalStats"),
        consumed_kwh=_kwh(production, "proConsumStats"),
        imported_kwh=_kwh(production, "proPurchaseStats"),
        exported_kwh=_kwh(production, "proGridStats"),
        points=points,
    )


class SemsModule(PollingModule[SemsFlow]):
    name = "sems"

    def __init__(self, cfg: SemsConfig, client: httpx.AsyncClient, tz: ZoneInfo) -> None:
        # Reintentos espaciados para no provocar bloqueos de la cuenta.
        super().__init__(cfg.poll_interval_seconds, retry_seconds=max(120, cfg.poll_interval_seconds))
        self._cfg = cfg
        self._client = client
        self._tz = tz
        self._session: dict[str, Any] | None = None
        # El módulo del resumen diario comparte la sesión: un único login a la vez.
        self._login_lock = asyncio.Lock()
        self._api = cfg.gateway.rstrip("/")

    def _headers(self, session: dict[str, Any] | None) -> dict[str, str]:
        token = {
            "uid": (session or {}).get("uid", ""),
            "timestamp": (session or {}).get("timestamp", 0),
            "token": (session or {}).get("token", ""),
            "client": CLIENT,
            "version": "",
            "language": "es",
        }
        return {
            "token": json.dumps(token),
            "x-signature": sign(token["uid"], token["token"]) if session else "",
            "currentlang": "es",
            "neutral": "0",
        }

    @staticmethod
    def _check(response: httpx.Response) -> Any:
        response.raise_for_status()
        body = response.json()
        code = body.get("code")
        if code not in OK_CODES:
            raise SemsError(code, body.get("description") or body.get("errorMsg") or body.get("msg") or "error")
        return body.get("data")

    async def _login(self) -> None:
        pwd = self._cfg.password_hash or hash_password(require_secret(self._cfg.password, "sems.password_hash"))
        require_secret(pwd, "sems.password_hash")
        response = await self._client.post(
            f"{self._cfg.gateway.rstrip('/')}/sems-user/api/v1/auth/cross-login",
            json={
                "account": self._cfg.username,
                "pwd": pwd,
                "agreement": 1,
                "isLocal": False,
                "isChinese": False,
            },
            headers=self._headers(None),
        )
        try:
            data = self._check(response) or {}
        except SemsError as exc:
            raise CredentialsError(f"SEMS rechazó el login: {exc}") from exc
        if data.get("mfaRequired"):
            raise SemsError("MFA", "La cuenta tiene verificación en dos pasos")
        self._session = data
        self._api = (data.get("api") or self._cfg.gateway).rstrip("/")
        self.log.info("Sesión de SEMS iniciada")

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        for attempt in range(2):
            async with self._login_lock:
                if self._session is None:
                    await self._login()
            response = await self._client.request(method, f"{self._api}{path}", headers=self._headers(self._session), **kwargs)
            try:
                return self._check(response)
            except SemsError as exc:
                if attempt == 0 and exc.code in AUTH_ERROR_CODES:
                    self._session = None  # sesión caducada: login y reintento
                    continue
                raise
        raise SemsError("AUTH", "No se pudo renovar la sesión")

    async def fetch(self) -> SemsFlow:
        data = await self._request("GET", "/sems-plant/api/stations/flow", params={"stationId": self._cfg.station_id})
        return parse_flow(data or {}, self._tz)

    async def fetch_day(self, day: date) -> SolarDay:
        """Totales y curva de potencia del día, como en la pantalla de inicio de SEMS+."""
        start = datetime.combine(day, dtime.min).strftime("%Y-%m-%d %H:%M:%S")
        end = datetime.combine(day, dtime(23, 59, 59)).strftime("%Y-%m-%d %H:%M:%S")
        # Como la web: desfase respecto a UTC con signo invertido (Madrid en verano = -2).
        # Las horas de la respuesta ya vienen en la hora local de la planta.
        offset = datetime.combine(day, dtime(12), self._tz).utcoffset()
        hours = -offset.total_seconds() / 3600 if offset else 0.0
        production = await self._request(
            "POST",
            "/sems-plant/api/stations/production",
            json={"stationId": self._cfg.station_id, "items": list(DAY_KPIS), "dimension": "day", "isReport": False, "startTime": start, "endTime": end},
        )
        curve = await self._request(
            "POST",
            "/sems-plant/api/v1/hems/power/statisticsAndPreV2",
            json={
                "stationId": self._cfg.station_id,
                "items": list(CURVE_ITEMS),
                "timeScale": 1,
                "timeZone": int(hours) if hours.is_integer() else hours,
                "startTime": start,
                "endTime": end,
            },
        )
        return parse_day(day, production or {}, curve or {})

    def fresh_snapshot(self) -> SemsFlow | None:
        """Última lectura si es reciente; SEMS se refresca cada pocos minutos."""
        snapshot = self.snapshot()
        if snapshot is None or snapshot.refreshed_at is None:
            return None
        age = (datetime.now(self._tz) - snapshot.refreshed_at).total_seconds()
        return snapshot if age <= self._cfg.max_age_minutes * 60 else None


class SolarDayModule(PollingModule[SolarDay]):
    """Resumen del día (totales y curva) para la tarjeta solar."""

    name = "solar_day"

    def __init__(self, sems: SemsModule, tz: ZoneInfo, interval_seconds: float = 300) -> None:
        super().__init__(interval_seconds, retry_seconds=120)
        self._sems = sems
        self._tz = tz

    async def fetch(self) -> SolarDay:
        return await self._sems.fetch_day(datetime.now(self._tz).date())
