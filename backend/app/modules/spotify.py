"""Spotify multi-cuenta: elige qué reproducción mostrar entre varias cuentas."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any

import httpx

from ..config import SpotifyAccount, SpotifyConfig
from ..schemas.models import NowPlaying, Track
from .base import PollingModule, utcnow

TOKEN_URL = "https://accounts.spotify.com/api/token"
PLAYER_URL = "https://api.spotify.com/v1/me/player"


@dataclass
class PlayerState:
    account: str
    is_playing: bool
    track: Track | None


class _AccountSession:
    def __init__(self, account: SpotifyAccount) -> None:
        self.account = account
        self.refresh_token = account.refresh_token
        self.access_token: str | None = None
        self.expires_at = 0.0


def parse_player(account: str, payload: dict[str, Any]) -> PlayerState:
    item = payload.get("item")
    device = payload.get("device") or {}
    track: Track | None = None
    if item:
        if item.get("type") == "episode":
            show = item.get("show") or {}
            artist = show.get("publisher") or show.get("name") or ""
            album = show.get("name") or ""
            images = item.get("images") or show.get("images") or []
        else:
            artist = ", ".join(a.get("name", "") for a in item.get("artists", []))
            album_info = item.get("album") or {}
            album = album_info.get("name", "")
            images = album_info.get("images") or []
        track = Track(
            title=item.get("name", ""),
            artist=artist,
            album=album,
            # Spotify ordena las imágenes de mayor a menor tamaño.
            album_art_url=images[0]["url"] if images else None,
            duration_ms=int(item.get("duration_ms") or 0),
            progress_ms=int(payload.get("progress_ms") or 0),
            device_name=device.get("name"),
        )
    return PlayerState(account=account, is_playing=bool(payload.get("is_playing")) and track is not None, track=track)


def select_playback(states: list[PlayerState | None], preferred_devices: list[str]) -> PlayerState | None:
    """1) una sola cuenta reproduciendo → esa; 2) varias → la que use un dispositivo
    preferido (por orden de la lista); 3) ninguna → ``None``."""
    playing = [s for s in states if s is not None and s.is_playing]
    if not playing:
        return None
    preferred = [name.casefold() for name in preferred_devices]

    def rank(state: PlayerState) -> int:
        device = (state.track.device_name or "").casefold() if state.track else ""
        return preferred.index(device) if device in preferred else len(preferred)

    return min(playing, key=rank)  # min es estable: a igualdad, la primera cuenta


class SpotifyModule(PollingModule[NowPlaying]):
    name = "spotify"

    def __init__(self, cfg: SpotifyConfig, client: httpx.AsyncClient) -> None:
        super().__init__(cfg.poll_interval_seconds, retry_seconds=15)
        self._cfg = cfg
        self._client = client
        self._sessions = [_AccountSession(account) for account in cfg.accounts]

    async def _token(self, session: _AccountSession) -> str:
        if session.access_token and time.monotonic() < session.expires_at - 60:
            return session.access_token
        response = await self._client.post(
            TOKEN_URL,
            data={"grant_type": "refresh_token", "refresh_token": session.refresh_token},
            auth=httpx.BasicAuth(self._cfg.client_id, self._cfg.client_secret),
        )
        response.raise_for_status()
        body = response.json()
        session.access_token = body["access_token"]
        session.expires_at = time.monotonic() + int(body.get("expires_in", 3600))
        # Spotify puede rotar el refresh token.
        session.refresh_token = body.get("refresh_token", session.refresh_token)
        return session.access_token

    async def _player(self, session: _AccountSession) -> PlayerState | None:
        for attempt in range(2):
            token = await self._token(session)
            response = await self._client.get(
                PLAYER_URL,
                params={"additional_types": "track,episode"},
                headers={"Authorization": f"Bearer {token}"},
            )
            if response.status_code == 401 and attempt == 0:
                session.access_token = None  # token revocado/caducado: renovar y reintentar
                continue
            if response.status_code == 204 or not response.content:
                return None
            response.raise_for_status()
            return parse_player(session.account.name, response.json())
        return None

    async def fetch(self) -> NowPlaying:
        results = await asyncio.gather(*(self._player(s) for s in self._sessions), return_exceptions=True)
        states: list[PlayerState | None] = []
        failures = 0
        for session, result in zip(self._sessions, results):
            if isinstance(result, BaseException):
                failures += 1
                self.report_source(session.account.name, result)
                states.append(None)
            else:
                self.report_source(session.account.name, None)
                states.append(result)

        if self._sessions and failures == len(self._sessions):
            raise RuntimeError("Ninguna cuenta de Spotify responde")

        chosen = select_playback(states, self._cfg.preferred_devices)
        status = "stale" if failures else "ok"
        if chosen is None:
            return NowPlaying(status=status, fetched_at=utcnow(), is_active=False)
        return NowPlaying(status=status, fetched_at=utcnow(), is_active=True, account=chosen.account, track=chosen.track)
