"""Calendarios iCal (.ics) con expansión de eventos recurrentes."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, tzinfo

import httpx
import icalendar
import recurring_ical_events

from ..config import CalendarsConfig, CalendarSource
from ..schemas.models import CalendarData, CalendarEvent
from .base import PollingModule, utcnow


@dataclass(frozen=True)
class _Event:
    id: str
    title: str
    start: datetime
    end: datetime
    is_all_day: bool
    calendar: str
    color: str
    location: str | None

    def to_model(self, now: datetime) -> CalendarEvent:
        return CalendarEvent(
            id=self.id,
            title=self.title,
            start=self.start,
            end=self.end,
            is_all_day=self.is_all_day,
            is_ongoing=self.start <= now < self.end,
            calendar=self.calendar,
            color=self.color,
            location=self.location,
        )


def _localize(value: datetime, tz: tzinfo) -> datetime:
    # Las horas "flotantes" (sin zona) se interpretan en la zona local.
    if value.tzinfo is None:
        return value.replace(tzinfo=tz)
    return value.astimezone(tz)


def parse_ics(raw: bytes, source: CalendarSource, start: datetime, end: datetime, tz: tzinfo) -> list[_Event]:
    calendar = icalendar.Calendar.from_ical(raw)
    events: list[_Event] = []
    for component in recurring_ical_events.of(calendar).between(start, end):
        if str(component.get("STATUS", "")).upper() == "CANCELLED":
            continue

        dtstart = component.get("DTSTART").dt
        if component.get("DTEND") is not None:
            dtend = component.get("DTEND").dt
        elif component.get("DURATION") is not None:
            dtend = dtstart + component.get("DURATION").dt
        else:
            dtend = dtstart if isinstance(dtstart, datetime) else dtstart + timedelta(days=1)

        is_all_day = not isinstance(dtstart, datetime)
        if is_all_day:
            ev_start = datetime.combine(dtstart, time.min, tz)
            end_date = dtend.date() if isinstance(dtend, datetime) else dtend
            ev_end = datetime.combine(max(end_date, dtstart + timedelta(days=1)), time.min, tz)
        else:
            ev_start = _localize(dtstart, tz)
            ev_end = _localize(dtend, tz) if isinstance(dtend, datetime) else datetime.combine(dtend, time.min, tz)

        uid = str(component.get("UID", ""))
        location = component.get("LOCATION")
        events.append(
            _Event(
                id=f"{source.name}:{uid}:{ev_start.isoformat()}",
                title=str(component.get("SUMMARY", "")).strip() or "(Sin título)",
                start=ev_start,
                end=ev_end,
                is_all_day=is_all_day,
                calendar=source.name,
                color=source.color,
                location=str(location).strip() or None if location is not None else None,
            )
        )
    return events


class CalendarModule(PollingModule[CalendarData]):
    name = "calendar"

    def __init__(self, cfg: CalendarsConfig, client: httpx.AsyncClient, tz: tzinfo) -> None:
        super().__init__(cfg.update_interval_minutes * 60)
        self._cfg = cfg
        self._client = client
        self._tz = tz
        self._events: list[_Event] = []
        # Última lectura válida por calendario, para tolerar fallos parciales.
        self._per_source: dict[str, list[_Event]] = {}

    def _window(self) -> tuple[datetime, datetime]:
        today: date = datetime.now(self._tz).date()
        start = datetime.combine(today, time.min, self._tz)
        end = datetime.combine(today + timedelta(days=self._cfg.days_ahead), time.max, self._tz)
        return start, end

    async def _fetch_source(self, source: CalendarSource, start: datetime, end: datetime) -> list[_Event]:
        response = await self._client.get(source.ics_url, follow_redirects=True)
        response.raise_for_status()
        return await asyncio.to_thread(parse_ics, response.content, source, start, end, self._tz)

    async def fetch(self) -> CalendarData:
        start, end = self._window()
        results = await asyncio.gather(
            *(self._fetch_source(source, start, end) for source in self._cfg.sources),
            return_exceptions=True,
        )

        failures = 0
        for source, result in zip(self._cfg.sources, results):
            if isinstance(result, BaseException):
                failures += 1
                self.report_source(source.name, result)
            else:
                self.report_source(source.name, None)
                self._per_source[source.name] = result

        if self._cfg.sources and failures == len(self._cfg.sources):
            raise RuntimeError("Ningún calendario disponible")

        events = [
            ev
            for source in self._cfg.sources
            for ev in self._per_source.get(source.name, [])
            if ev.end > start  # descarta restos de ventanas de días anteriores
        ]
        events.sort(key=lambda ev: (ev.start, not ev.is_all_day, ev.title))
        self._events = events
        return self._build(status="stale" if failures else "ok")

    def _build(self, status: str) -> CalendarData:
        now = datetime.now(self._tz)
        return CalendarData(
            status=status,
            fetched_at=utcnow(),
            events=[ev.to_model(now) for ev in self._events],
        )

    def snapshot(self) -> CalendarData | None:
        # ``is_ongoing`` se recalcula en cada petición: los datos se refrescan
        # cada varios minutos pero el flag debe ser preciso.
        base = super().snapshot()
        if base is None:
            return None
        now = datetime.now(self._tz)
        return base.model_copy(update={"events": [ev.to_model(now) for ev in self._events]})
