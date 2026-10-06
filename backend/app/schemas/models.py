"""Modelos Pydantic v2 de las respuestas de la API.

Todos los modelos son estrictos (sin coerción de tipos ni campos extra) para
detectar en el propio backend cualquier desajuste al normalizar los datos de
los servicios externos.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

DataStatus = Literal["ok", "stale"]


class StrictModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


class ModuleData(StrictModel):
    """Base de toda respuesta de módulo.

    ``status`` pasa a ``"stale"`` cuando la última consulta al servicio falló y
    se está sirviendo la última lectura válida.
    """

    status: DataStatus = "ok"
    fetched_at: datetime


# ── Solar ────────────────────────────────────────────────────────────────────


class SolarData(ModuleData):
    ppv: float
    """Potencia fotovoltaica instantánea (W)."""
    house_consumption: float | None
    """Potencia demandada por el hogar (W). ``None`` si el inversor no tiene medidor."""
    active_power: float | None
    """Flujo de red (W): positivo = inyección a red, negativo = consumo de red.
    ``None`` si el inversor no tiene medidor."""
    battery_power: float | None = None
    """Potencia de batería (W): positivo = descarga, negativo = carga."""
    battery_soc: float | None = None
    today_energy_kwh: float
    inverter_model: str | None = None
    flow_source: Literal["inverter", "balance", "sems"] | None = None
    """Origen de consumo/red: medidor del inversor; "balance" = hogar de SEMS y
    red estimada en vivo (FV − hogar); "sems" = ambos de SEMS (inversor apagado)."""
    flow_updated_at: datetime | None = None
    """Hora de la lectura de SEMS (solo si ``flow_source == "sems"``)."""


class SemsFlow(ModuleData):
    pv_w: float
    house_w: float
    grid_w: float
    """W: positivo = inyección a red, negativo = consumo de red."""
    refreshed_at: datetime | None


# ── Calendario ───────────────────────────────────────────────────────────────


class CalendarEvent(StrictModel):
    id: str
    title: str
    start: datetime
    end: datetime
    is_all_day: bool
    is_ongoing: bool
    calendar: str
    color: str
    location: str | None = None


class CalendarData(ModuleData):
    events: list[CalendarEvent]


# ── Meteorología ─────────────────────────────────────────────────────────────


class CurrentWeather(StrictModel):
    temperature: float
    apparent_temperature: float
    humidity: float
    wind_speed: float
    weather_code: int
    is_day: bool


class HourlyForecast(StrictModel):
    time: datetime
    temperature: float
    weather_code: int
    precipitation_probability: int | None
    is_day: bool


class DailyForecast(StrictModel):
    date: date
    temperature_min: float
    temperature_max: float
    weather_code: int
    precipitation_probability_max: int | None
    sunrise: datetime | None
    sunset: datetime | None


class WeatherData(ModuleData):
    location: str
    current: CurrentWeather
    hourly: list[HourlyForecast]
    daily: list[DailyForecast]


class WeatherLocationInfo(StrictModel):
    index: int
    name: str


# ── Google Keep ──────────────────────────────────────────────────────────────


class ShoppingItem(StrictModel):
    id: str
    text: str
    completed: bool


class ShoppingList(ModuleData):
    title: str
    updated_at: datetime | None
    items: list[ShoppingItem]


# ── NAS (OpenMediaVault) ─────────────────────────────────────────────────────


class NasCpu(StrictModel):
    usage_percent: float


class NasMemory(StrictModel):
    total_gb: float
    used_gb: float
    percent: float


class NasVolume(StrictModel):
    mount_point: str
    label: str
    total_gb: float
    used_gb: float
    percent: float


class NasStatus(ModuleData):
    status: Literal["healthy", "degraded", "stale"] = "healthy"  # type: ignore[assignment]
    hostname: str | None = None
    uptime_seconds: int | None = None
    cpu: NasCpu
    memory: NasMemory
    storage: list[NasVolume]


# ── AdGuard Home ─────────────────────────────────────────────────────────────


class AdguardStats(ModuleData):
    protection_enabled: bool
    queries_24h: int
    blocked_24h: int
    block_ratio_percent: float


# ── Spotify ──────────────────────────────────────────────────────────────────


class Track(StrictModel):
    title: str
    artist: str
    album: str
    album_art_url: str | None
    duration_ms: int
    progress_ms: int
    device_name: str | None


class NowPlaying(ModuleData):
    is_active: bool
    account: str | None = None
    track: Track | None = None


# ── Noticias ─────────────────────────────────────────────────────────────────


class NewsItem(StrictModel):
    id: str
    title: str
    source: str
    link: str | None
    published_at: datetime | None


class NewsData(ModuleData):
    ticker_speed_seconds: int
    items: list[NewsItem]


# ── Salud ────────────────────────────────────────────────────────────────────


class ModuleHealth(StrictModel):
    status: Literal["ok", "stale", "pending"]
    last_success: datetime | None
    last_error: str | None


class HealthResponse(StrictModel):
    modules: dict[str, ModuleHealth]
