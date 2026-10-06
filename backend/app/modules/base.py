"""Infraestructura común: cada módulo es una tarea asíncrona independiente que
sondea su servicio y conserva la última lectura válida."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Generic, TypeVar

from ..schemas.models import ModuleData, ModuleHealth

T = TypeVar("T", bound=ModuleData)

Listener = Callable[[ModuleData], Awaitable[None]]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PollingModule(Generic[T]):
    """Ejecuta ``fetch()`` cada ``interval`` segundos.

    Si ``fetch()`` falla, la excepción se registra y se sigue sirviendo la
    última lectura válida marcada como ``stale``; el reintento se hace antes
    (``retry``) que el intervalo normal cuando éste es largo.
    """

    name = "module"

    def __init__(self, interval_seconds: float, retry_seconds: float = 30) -> None:
        self.interval = interval_seconds
        self.retry = min(interval_seconds, retry_seconds)
        self.log = logging.getLogger(f"dashboard.{self.name}")
        self._data: T | None = None
        self._failing = False
        self._last_error: str | None = None
        self._last_success: datetime | None = None
        self._listeners: list[Listener] = []
        self._task: asyncio.Task[None] | None = None
        self._failing_sources: set[str] = set()

    async def fetch(self) -> T:
        raise NotImplementedError

    async def close(self) -> None:
        """Libera recursos propios del módulo (clientes HTTP, etc.)."""

    def subscribe(self, listener: Listener) -> None:
        self._listeners.append(listener)

    def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name=f"poll:{self.name}")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self.close()

    async def _run(self) -> None:
        while True:
            delay = await self.refresh()
            await asyncio.sleep(delay)

    async def refresh(self) -> float:
        """Ejecuta una actualización y devuelve los segundos hasta la siguiente."""
        try:
            data = await self.fetch()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - un módulo nunca debe tumbar la API
            self._last_error = f"{type(exc).__name__}: {exc}"
            # Solo el primer fallo de una racha va a WARNING para no inundar el log
            # (p. ej. un inversor sin fotovoltaica que se apaga por la noche).
            level = logging.DEBUG if self._failing else logging.WARNING
            self.log.log(level, "Actualización fallida: %s", self._last_error, exc_info=self.log.isEnabledFor(logging.DEBUG))
            self._failing = True
            await self._notify()
            return self.retry

        if self._failing:
            self.log.info("Servicio recuperado")
        self._data = data
        self._failing = False
        self._last_error = None
        self._last_success = utcnow()
        await self._notify()
        return self.interval

    def report_source(self, source: str, error: BaseException | None) -> None:
        """Registra el estado de una subfuente (calendario, feed, cuenta...) y solo
        loguea los cambios, no cada fallo repetido."""
        if error is None:
            if source in self._failing_sources:
                self._failing_sources.discard(source)
                self.log.info("'%s' recuperado", source)
        elif source not in self._failing_sources:
            self._failing_sources.add(source)
            self.log.warning("'%s' no disponible: %s", source, error)

    def snapshot(self) -> T | None:
        if self._data is None:
            return None
        if self._failing:
            return self._data.model_copy(update={"status": "stale"})
        return self._data

    def health(self) -> ModuleHealth:
        if self._data is None:
            status = "stale" if self._failing else "pending"
        else:
            status = "stale" if self._failing else "ok"
        return ModuleHealth(status=status, last_success=self._last_success, last_error=self._last_error)

    async def _notify(self) -> None:
        snapshot = self.snapshot()
        if snapshot is None:
            return
        for listener in self._listeners:
            try:
                await listener(snapshot)
            except Exception:  # noqa: BLE001
                self.log.exception("Error notificando a un suscriptor")
