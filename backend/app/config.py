"""Carga y validación de la configuración centralizada (config.yaml)."""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class _Section(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ServerConfig(_Section):
    host: str = "0.0.0.0"
    port: int = 3080
    timezone: str = "Europe/Madrid"
    log_level: str = "INFO"

    @field_validator("timezone")
    @classmethod
    def _valid_timezone(cls, value: str) -> str:
        ZoneInfo(value)  # lanza si la zona no existe
        return value

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


class InverterConfig(_Section):
    enabled: bool = True
    ip_address: str
    family: str | None = None  # ET, ES, DT... None = autodetección
    poll_interval_seconds: float = Field(default=10, gt=0)


class SemsConfig(_Section):
    """Nube de GoodWe (SEMS+): consumo del hogar y red cuando el inversor no tiene medidor."""

    enabled: bool = True
    username: str
    # Preferible password_hash (scripts/sems_hash.py): la contraseña no queda escrita.
    password_hash: str | None = None
    password: str | None = None
    station_id: str
    gateway: str = "https://eu-gateway.semsportal.com/web/sems"
    poll_interval_seconds: float = Field(default=60, gt=0)
    max_age_minutes: float = Field(default=15, gt=0)

    @model_validator(mode="after")
    def _requires_credentials(self) -> SemsConfig:
        if not self.password_hash and not self.password:
            raise ValueError("sems: se requiere 'password_hash' (recomendado) o 'password'")
        return self


class WeatherLocation(_Section):
    name: str
    latitude: float
    longitude: float


class WeatherConfig(_Section):
    """La primera ubicación es la principal (widget completo); el resto se
    muestran como tarjetas compactas."""

    enabled: bool = True
    update_interval_minutes: float = Field(default=5, gt=0)
    locations: list[WeatherLocation] = Field(min_length=1)


class CalendarSource(_Section):
    name: str
    color: str = "#38bdf8"
    ics_url: str


class CalendarsConfig(_Section):
    enabled: bool = True
    update_interval_minutes: float = Field(default=10, gt=0)
    days_ahead: int = Field(default=21, ge=1, le=90)  # días a mostrar además de hoy
    sources: list[CalendarSource] = Field(default_factory=list)


class KeepConfig(_Section):
    enabled: bool = True
    username: str
    # Contraseña de aplicación o master token ("aas_et/...").
    password: str | None = None
    master_token: str | None = None
    target_list_title: str = "La Compra"  # sin distinguir mayúsculas
    completed_items_shown: int = Field(default=0, ge=0)  # elementos marcados a mostrar (0 = solo pendientes)
    poll_interval_seconds: float = Field(default=30, gt=0)


class OmvConfig(_Section):
    enabled: bool = True
    url: str = "http://127.0.0.1:80"
    username: str = "admin"
    password: str
    poll_interval_seconds: float = Field(default=60, gt=0)
    exclude_mount_points: list[str] = Field(default_factory=lambda: ["/", "/boot", "/boot/efi"])


class AdguardConfig(_Section):
    enabled: bool = True
    url: str = "http://127.0.0.1:80"  # panel web de AdGuard (no el 3000 del asistente)
    username: str
    password: str
    poll_interval_seconds: float = Field(default=300, gt=0)


class SpotifyAccount(_Section):
    name: str
    refresh_token: str


class SpotifyConfig(_Section):
    enabled: bool = True
    client_id: str
    client_secret: str
    poll_interval_seconds: float = Field(default=5, gt=0)
    accounts: list[SpotifyAccount] = Field(default_factory=list)
    preferred_devices: list[str] = Field(default_factory=list)


class NewsFeed(_Section):
    name: str
    url: str


class NewsConfig(_Section):
    enabled: bool = True
    update_interval_minutes: float = Field(default=30, gt=0)
    ticker_speed_seconds: int = Field(default=15, gt=0)
    max_items: int = Field(default=25, gt=0)
    feeds: list[NewsFeed] = Field(default_factory=list)


class AppConfig(_Section):
    """Una sección ausente equivale a módulo deshabilitado."""

    server: ServerConfig = Field(default_factory=ServerConfig)
    inverter: InverterConfig | None = None
    sems: SemsConfig | None = None
    weather: WeatherConfig | None = None
    calendars: CalendarsConfig | None = None
    keep: KeepConfig | None = None
    omv: OmvConfig | None = None
    adguard: AdguardConfig | None = None
    spotify: SpotifyConfig | None = None
    news: NewsConfig | None = None


_ENV_REF = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")

# Variables referenciadas en config.yaml que no estaban definidas (se loguean al arrancar).
MISSING_ENV: set[str] = set()


def expand_env(value: Any, missing: set[str]) -> Any:
    """Sustituye ``${VAR}`` por la variable de entorno, para no escribir secretos
    en config.yaml. Una variable ausente se deja vacía y se anota en ``missing``:
    fallará solo el módulo que la usa, no el arranque."""
    if isinstance(value, dict):
        return {k: expand_env(v, missing) for k, v in value.items()}
    if isinstance(value, list):
        return [expand_env(v, missing) for v in value]
    if isinstance(value, str):

        def resolve(match: re.Match[str]) -> str:
            name = match.group(1)
            if not os.environ.get(name):
                missing.add(name)
            return os.environ.get(name, "")

        return _ENV_REF.sub(resolve, value)
    return value


def load_config(path: str | os.PathLike[str] | None = None) -> AppConfig:
    config_path = Path(path or os.environ.get("CONFIG_PATH", "config.yaml"))
    with config_path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    MISSING_ENV.clear()
    return AppConfig.model_validate(expand_env(raw, MISSING_ENV))


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    return load_config()
