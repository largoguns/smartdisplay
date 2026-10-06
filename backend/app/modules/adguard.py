"""Estadísticas de AdGuard Home (``/control/stats`` y ``/control/status``)."""

from __future__ import annotations

import asyncio

import httpx

from ..config import AdguardConfig
from ..schemas.models import AdguardStats
from .base import PollingModule, utcnow


class AdguardModule(PollingModule[AdguardStats]):
    name = "adguard"

    def __init__(self, cfg: AdguardConfig, client: httpx.AsyncClient) -> None:
        super().__init__(cfg.poll_interval_seconds, retry_seconds=60)
        self._cfg = cfg
        self._client = client
        self._base = cfg.url.rstrip("/")
        self._auth = httpx.BasicAuth(cfg.username, cfg.password)

    async def _get(self, path: str) -> dict:
        response = await self._client.get(f"{self._base}{path}", auth=self._auth)
        response.raise_for_status()
        return response.json()

    async def fetch(self) -> AdguardStats:
        stats, status = await asyncio.gather(self._get("/control/stats"), self._get("/control/status"))
        queries = int(stats.get("num_dns_queries", 0))
        blocked = sum(
            int(stats.get(key, 0))
            for key in ("num_blocked_filtering", "num_replaced_safebrowsing", "num_replaced_parental")
        )
        return AdguardStats(
            fetched_at=utcnow(),
            protection_enabled=bool(status.get("protection_enabled", False)),
            queries_24h=queries,
            blocked_24h=blocked,
            block_ratio_percent=round(blocked / queries * 100, 1) if queries else 0.0,
        )
