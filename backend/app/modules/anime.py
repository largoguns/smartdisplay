"""Capítulos nuevos de las series seguidas en la app de seguimiento de anime."""

from __future__ import annotations

from typing import Any

import httpx

from ..config import AnimeConfig
from ..schemas.models import AnimeData, AnimeEpisode
from .base import PollingModule, utcnow

# El refresco consulta cada serie en su web de origen: tarda más que una API normal.
REFRESH_TIMEOUT_SECONDS = 60


def parse_tracking(payload: dict[str, Any]) -> list[AnimeEpisode]:
    if not payload.get("ok", False):
        raise RuntimeError(f"La app de anime respondió con error: {payload.get('error') or payload}")
    return [
        AnimeEpisode(
            id=int(entry["id"]),
            title=str(entry.get("anime_title") or entry.get("latest_title") or "?"),
            thumbnail_url=entry.get("thumbnail_url") or None,
            new_count=int(entry.get("new_count") or 0),
        )
        for entry in payload.get("tracking", [])
        if (entry.get("new_count") or 0) > 0
    ]


class AnimeModule(PollingModule[AnimeData]):
    name = "anime"

    def __init__(self, cfg: AnimeConfig, client: httpx.AsyncClient) -> None:
        super().__init__(cfg.poll_interval_seconds, retry_seconds=300)
        self._client = client
        self._refresh_url = f"{cfg.url.rstrip('/')}/api/tracking/refresh"

    async def fetch(self) -> AnimeData:
        response = await self._client.post(self._refresh_url, timeout=REFRESH_TIMEOUT_SECONDS)
        response.raise_for_status()
        return AnimeData(fetched_at=utcnow(), items=parse_tracking(response.json()))
