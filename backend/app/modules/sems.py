"""Flujo de energía desde SEMS+ (nube de GoodWe).

Complementa al inversor local cuando éste no tiene medidor: el consumo del
hogar y el intercambio con la red los mide el HomeKit, que solo los publica en
SEMS. API no oficial, la misma que usa la web semsplus.goodwe.com.
"""

from __future__ import annotations

import base64
import hashlib
import json
import time
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from ..config import SemsConfig
from ..schemas.models import SemsFlow
from .base import PollingModule, utcnow

OK_CODES = ("00000", "0", 0)
# Sesión caducada o inválida: hay que repetir el login.
AUTH_ERROR_CODES = ("C0602", "C0607", "A0301", "100002", 100002)
CLIENT = "semsPlusWeb"


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
    {"pSystem": ["pConsum", "pGrid"]} = exportando, {"pGrid": [...]} = importando."""
    flows: dict[str, list[str]] = data.get("flows") or {}
    grid_kw = float(data.get("pGrid") or 0.0)
    if "pGrid" in flows and flows["pGrid"]:
        grid_w = -grid_kw * 1000
    elif any("pGrid" in targets for targets in flows.values()):
        grid_w = grid_kw * 1000
    else:
        grid_w = 0.0

    refreshed = data.get("refreshTime")
    return SemsFlow(
        fetched_at=utcnow(),
        pv_w=round(float(data.get("pSystem") or 0.0) * 1000, 1),
        house_w=round(float(data.get("pConsum") or 0.0) * 1000, 1),
        grid_w=round(grid_w, 1),
        refreshed_at=datetime.fromisoformat(refreshed).replace(tzinfo=tz) if refreshed else None,
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
        response = await self._client.post(
            f"{self._cfg.gateway.rstrip('/')}/sems-user/api/v1/auth/cross-login",
            json={
                "account": self._cfg.username,
                "pwd": self._cfg.password_hash or hash_password(self._cfg.password or ""),
                "agreement": 1,
                "isLocal": False,
                "isChinese": False,
            },
            headers=self._headers(None),
        )
        data = self._check(response) or {}
        if data.get("mfaRequired"):
            raise SemsError("MFA", "La cuenta tiene verificación en dos pasos")
        self._session = data
        self._api = (data.get("api") or self._cfg.gateway).rstrip("/")
        self.log.info("Sesión de SEMS iniciada")

    async def _get(self, path: str, params: dict[str, Any]) -> Any:
        for attempt in range(2):
            if self._session is None:
                await self._login()
            response = await self._client.get(f"{self._api}{path}", params=params, headers=self._headers(self._session))
            try:
                return self._check(response)
            except SemsError as exc:
                if attempt == 0 and exc.code in AUTH_ERROR_CODES:
                    self._session = None  # sesión caducada: login y reintento
                    continue
                raise
        raise SemsError("AUTH", "No se pudo renovar la sesión")

    async def fetch(self) -> SemsFlow:
        data = await self._get("/sems-plant/api/stations/flow", {"stationId": self._cfg.station_id})
        return parse_flow(data or {}, self._tz)

    def fresh_snapshot(self) -> SemsFlow | None:
        """Última lectura si es reciente; SEMS se refresca cada pocos minutos."""
        snapshot = self.snapshot()
        if snapshot is None or snapshot.refreshed_at is None:
            return None
        age = (datetime.now(self._tz) - snapshot.refreshed_at).total_seconds()
        return snapshot if age <= self._cfg.max_age_minutes * 60 else None
