"""Inversor GoodWe vía UDP en la LAN (librería ``goodwe``)."""

from __future__ import annotations

import re
from datetime import date, datetime, tzinfo
from typing import Any

import goodwe

from ..config import InverterConfig
from ..schemas.models import SemsFlow, SolarData
from .base import PollingModule, utcnow
from .sems import SemsModule

_PV_STRING_KEY = re.compile(r"^ppv\d+$")


def _num(data: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = data.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return None


def parse_runtime_data(data: dict[str, Any], model: str | None = None) -> SolarData:
    """Normaliza los sensores de las distintas familias (ET/ES/DT...)."""
    ppv = _num(data, "ppv", "ppv_total")
    if ppv is None:
        strings = [float(v) for k, v in data.items() if _PV_STRING_KEY.match(k) and isinstance(v, (int, float))]
        ppv = sum(strings) if strings else 0.0

    battery_power = _num(data, "pbattery1", "battery_power")
    battery_soc = _num(data, "battery_soc")

    # Flujo de red: solo si hay medidor. Los DT sin medidor (meter_comm_status 0)
    # devuelven meter_active_power = -1 y un house_consumption que es la propia
    # producción FV; ninguno de los dos significa nada.
    active_power = _num(data, "active_power", "grid_active_power")
    if active_power is None and data.get("meter_comm_status"):
        active_power = _num(data, "meter_active_power")

    house: float | None = None
    if active_power is not None:
        house = _num(data, "house_consumption", "load_ptotal")
        if house is None:
            # Balance: lo que entra (FV + descarga de batería) menos lo que se inyecta.
            house = max(0.0, ppv + (battery_power or 0.0) - active_power)

    return SolarData(
        fetched_at=utcnow(),
        ppv=round(ppv, 1),
        house_consumption=round(house, 1) if house is not None else None,
        active_power=round(active_power, 1) if active_power is not None else None,
        battery_power=round(battery_power, 1) if battery_power is not None else None,
        battery_soc=battery_soc,
        today_energy_kwh=round(_num(data, "e_day", "e_day_exp") or 0.0, 2),
        inverter_model=model,
    )


def merge_with_sems(local: SolarData | None, cloud: SemsFlow | None, today_kwh: float) -> SolarData | None:
    """Completa la lectura local con el flujo de SEMS cuando el inversor no mide la red.

    - Inversor + SEMS ("balance"): el consumo del hogar es el de SEMS (cada ~2 min)
      y la red se recalcula en vivo con la FV local: red = FV + batería − hogar.
      Así los tres valores cuadran y la red reacciona al instante a las nubes.
    - Solo SEMS (inversor apagado de noche): sus valores tal cual.
    """
    if local is not None and (local.active_power is not None or cloud is None):
        return local.model_copy(update={"flow_source": "inverter" if local.active_power is not None else None})
    if cloud is None:
        return None
    if local is not None:
        grid = local.ppv + (local.battery_power or 0.0) - cloud.house_w
        return local.model_copy(
            update={
                "house_consumption": cloud.house_w,
                "active_power": round(grid, 1),
                "flow_source": "balance",
                "flow_updated_at": cloud.refreshed_at,
            }
        )
    return SolarData(
        fetched_at=utcnow(),
        ppv=cloud.pv_w,
        house_consumption=cloud.house_w,
        active_power=cloud.grid_w,
        today_energy_kwh=today_kwh,
        flow_source="sems",
        flow_updated_at=cloud.refreshed_at,
    )


class SolarModule(PollingModule[SolarData]):
    name = "solar"

    def __init__(self, cfg: InverterConfig | None, sems: SemsModule | None, tz: tzinfo) -> None:
        super().__init__(cfg.poll_interval_seconds if cfg else 60)
        self._cfg = cfg
        self._sems = sems
        self._tz = tz
        self._inverter: goodwe.Inverter | None = None
        # Última energía del día leída del inversor, para cuando se apaga de noche.
        self._today: tuple[date, float] | None = None

    async def _read_inverter(self) -> SolarData:
        assert self._cfg is not None
        if self._inverter is None:
            self._inverter = await goodwe.connect(
                host=self._cfg.ip_address,
                family=self._cfg.family,
                timeout=2,
                retries=3,
            )
            self.log.info("Conectado a inversor %s", getattr(self._inverter, "model_name", "GoodWe"))
        data = await self._inverter.read_runtime_data()
        return parse_runtime_data(data, getattr(self._inverter, "model_name", None))

    def _today_kwh(self) -> float:
        today = datetime.now(self._tz).date()
        return self._today[1] if self._today and self._today[0] == today else 0.0

    async def fetch(self) -> SolarData:
        local: SolarData | None = None
        error: Exception | None = None
        if self._cfg is not None:
            try:
                local = await self._read_inverter()
                self._today = (datetime.now(self._tz).date(), local.today_energy_kwh)
            except Exception as exc:  # noqa: BLE001 - se decide abajo si es fatal
                error = exc

        cloud = self._sems.fresh_snapshot() if self._sems else None
        merged = merge_with_sems(local, cloud, self._today_kwh())
        if merged is None:
            raise error or RuntimeError("Sin datos del inversor ni de SEMS")
        # Con SEMS cubriendo, el inversor apagado no es un fallo del módulo.
        self.report_source("inversor", error)
        return merged
