"""Lista de la compra en Google Keep (``gkeepapi``, síncrono → hilo aparte)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import gkeepapi
from gkeepapi.node import List as KeepList

from ..config import KeepConfig
from ..schemas.models import ShoppingItem, ShoppingList
from .base import PollingModule, utcnow


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    # gkeepapi devuelve marcas de tiempo UTC sin zona.
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _updated(node: Any) -> datetime:
    return _aware(getattr(node.timestamps, "updated", None)) or datetime.min.replace(tzinfo=timezone.utc)


class KeepModule(PollingModule[ShoppingList]):
    name = "keep"

    def __init__(self, cfg: KeepConfig) -> None:
        # Reintentos espaciados: los reintentos de login agresivos pueden
        # provocar bloqueos temporales de la cuenta en Google.
        super().__init__(cfg.poll_interval_seconds, retry_seconds=max(120, cfg.poll_interval_seconds))
        self._cfg = cfg
        self._keep: gkeepapi.Keep | None = None

    def _login(self) -> gkeepapi.Keep:
        keep = gkeepapi.Keep()
        token = self._cfg.master_token
        if token is None and self._cfg.password and self._cfg.password.startswith("aas_et/"):
            token = self._cfg.password
        if token:
            keep.authenticate(self._cfg.username, token)
        elif self._cfg.password:
            keep.login(self._cfg.username, self._cfg.password)
        else:
            raise ValueError("keep: se requiere 'password' o 'master_token'")
        self.log.info("Sesión de Google Keep iniciada")
        return keep

    def _fetch_sync(self) -> ShoppingList:
        if self._keep is None:
            self._keep = self._login()
        else:
            try:
                self._keep.sync()
            except Exception:
                self._keep = None  # fuerza un nuevo login en el próximo ciclo
                raise

        title = self._cfg.target_list_title.strip().casefold()
        candidates = [
            node
            for node in self._keep.find(func=lambda n: isinstance(n, KeepList) and n.title.strip().casefold() == title)
            if not node.trashed
        ]
        if not candidates:
            raise LookupError(f"No existe ninguna lista de Keep titulada '{self._cfg.target_list_title}'")
        # Si hubiera varias (p. ej. una antigua archivada), la no archivada y más reciente.
        target = max(candidates, key=lambda n: (not n.archived, _updated(n)))

        pending = [item for item in target.unchecked if item.text.strip()]
        completed = sorted((item for item in target.checked if item.text.strip()), key=_updated, reverse=True)

        return ShoppingList(
            fetched_at=utcnow(),
            title=target.title,
            updated_at=_aware(getattr(target.timestamps, "updated", None)),
            items=[
                ShoppingItem(id=str(item.id), text=item.text.strip(), completed=bool(item.checked))
                for item in [*pending, *completed[: self._cfg.completed_items_shown]]
            ],
        )

    async def fetch(self) -> ShoppingList:
        return await asyncio.to_thread(self._fetch_sync)
