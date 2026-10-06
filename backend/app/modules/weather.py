"""Cliente Open-Meteo (sin API key)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from ..config import WeatherLocation
from ..schemas.models import CurrentWeather, DailyForecast, HourlyForecast, WeatherData
from .base import PollingModule, utcnow

API_URL = "https://api.open-meteo.com/v1/forecast"
HOURLY_HOURS = 12
DAILY_DAYS = 5


def _opt_int(value: Any) -> int | None:
    return int(value) if value is not None else None


def _parse_time(value: str | None, tz: ZoneInfo) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value).replace(tzinfo=tz)


def parse_forecast(payload: dict[str, Any], location: str) -> WeatherData:
    tz = ZoneInfo(payload.get("timezone") or "UTC")
    cur = payload["current"]
    current = CurrentWeather(
        temperature=float(cur["temperature_2m"]),
        apparent_temperature=float(cur["apparent_temperature"]),
        humidity=float(cur["relative_humidity_2m"]),
        wind_speed=float(cur["wind_speed_10m"]),
        weather_code=int(cur["weather_code"]),
        is_day=bool(cur["is_day"]),
    )

    # Próximas horas a partir de la hora en curso.
    now_hour = datetime.fromisoformat(cur["time"]).replace(minute=0, tzinfo=tz)
    h = payload["hourly"]
    hourly: list[HourlyForecast] = []
    for i, raw_time in enumerate(h["time"]):
        when = datetime.fromisoformat(raw_time).replace(tzinfo=tz)
        if when <= now_hour:
            continue
        hourly.append(
            HourlyForecast(
                time=when,
                temperature=float(h["temperature_2m"][i]),
                weather_code=int(h["weather_code"][i]),
                precipitation_probability=_opt_int(h["precipitation_probability"][i]),
                is_day=bool(h["is_day"][i]),
            )
        )
        if len(hourly) == HOURLY_HOURS:
            break

    d = payload["daily"]
    daily = [
        DailyForecast(
            date=date.fromisoformat(d["time"][i]),
            temperature_min=float(d["temperature_2m_min"][i]),
            temperature_max=float(d["temperature_2m_max"][i]),
            weather_code=int(d["weather_code"][i]),
            precipitation_probability_max=_opt_int(d["precipitation_probability_max"][i]),
            sunrise=_parse_time(d["sunrise"][i], tz),
            sunset=_parse_time(d["sunset"][i], tz),
        )
        for i in range(min(DAILY_DAYS, len(d["time"])))
    ]

    return WeatherData(fetched_at=utcnow(), location=location, current=current, hourly=hourly, daily=daily)


class WeatherModule(PollingModule[WeatherData]):
    """Una instancia por ubicación configurada."""

    name = "weather"

    def __init__(self, location: WeatherLocation, interval_minutes: float, client: httpx.AsyncClient) -> None:
        self.name = f"weather:{location.name}"
        super().__init__(interval_minutes * 60, retry_seconds=60)
        self.location = location
        self._client = client

    async def fetch(self) -> WeatherData:
        params = {
            "latitude": self.location.latitude,
            "longitude": self.location.longitude,
            "current": "temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,weather_code,is_day",
            "hourly": "temperature_2m,weather_code,precipitation_probability,is_day",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,sunrise,sunset",
            "timezone": "auto",
            "forecast_days": DAILY_DAYS + 1,  # margen para las 12 h siguientes cerca de medianoche
            "wind_speed_unit": "kmh",
        }
        response = await self._client.get(API_URL, params=params)
        response.raise_for_status()
        return parse_forecast(response.json(), self.location.name)
