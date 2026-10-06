"""Cliente JSON-RPC de OpenMediaVault (``/rpc.php``)."""

from __future__ import annotations

from collections import deque
from typing import Any

import httpx

from ..config import OmvConfig
from ..schemas.models import NasCpu, NasMemory, NasStatus, NasVolume
from .base import CredentialsError, PollingModule, require_secret, utcnow

GB = 1024**3
DEGRADED_STORAGE_PERCENT = 90.0
DEGRADED_MEMORY_PERCENT = 95.0
CPU_SMOOTHING_SAMPLES = 3


class OmvRpcError(Exception):
    def __init__(self, code: int | None, message: str) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code

    @property
    def is_auth_error(self) -> bool:
        # 5001 no autenticado, 5002 sesión expirada, 5003 IP de sesión inválida...
        return self.code is not None and 5000 <= self.code < 5100


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_system_info(info: Any) -> tuple[NasCpu, NasMemory, str | None, int | None]:
    # OMV <= 4 devolvía una lista de pares {name, value}.
    if isinstance(info, list):
        info = {entry.get("name"): entry.get("value") for entry in info if isinstance(entry, dict)}

    # OMV 8 lo llama cpuUtilization; versiones anteriores, cpuUsage.
    cpu = _float(info.get("cpuUtilization"))
    if cpu is None:
        cpu = _float(info.get("cpuUsage")) or 0.0
    total = _float(info.get("memTotal")) or 0.0
    available = _float(info.get("memAvailable"))
    used = total - available if available is not None else (_float(info.get("memUsed")) or 0.0)
    uptime = _float(info.get("uptime"))

    memory = NasMemory(
        total_gb=round(total / GB, 1),
        used_gb=round(used / GB, 1),
        percent=round(used / total * 100, 1) if total else 0.0,
    )
    hostname = info.get("hostname")
    return (
        NasCpu(usage_percent=round(cpu, 1)),
        memory,
        str(hostname) if hostname else None,
        int(uptime) if uptime is not None else None,
    )


def _volume_label(fs: dict[str, Any], mount_point: str) -> str:
    """Etiqueta del volumen o, si no tiene, el dispositivo corto (/dev/sdb1).
    ``description`` es "/dev/sdb1 [EXT4, 514 GiB ...]" y ``devicefile`` suele ser
    la ruta by-uuid, ninguno legible en pantalla."""
    if fs.get("label"):
        return str(fs["label"])
    for key in ("canonicaldevicefile", "description", "devicefile"):
        value = str(fs.get(key) or "").split(" [")[0].strip()
        if value:
            return value
    return mount_point


def parse_filesystems(response: Any, exclude: list[str]) -> list[NasVolume]:
    rows = response.get("data", []) if isinstance(response, dict) else response or []
    volumes: list[NasVolume] = []
    for fs in rows:
        mount_point = fs.get("mountpoint") or fs.get("mountdir") or ""
        if not fs.get("mounted") or not mount_point or mount_point in exclude:
            continue
        size = _float(fs.get("size")) or 0.0
        if size <= 0:
            continue
        available = _float(fs.get("available"))
        used = size - available if available is not None else (_float(fs.get("used")) or 0.0)
        percent = _float(fs.get("percentage"))
        volumes.append(
            NasVolume(
                mount_point=mount_point,
                label=_volume_label(fs, mount_point),
                total_gb=round(size / GB, 1),
                used_gb=round(used / GB, 1),
                percent=round(percent if percent is not None else used / size * 100, 1),
            )
        )
    return volumes


class NasModule(PollingModule[NasStatus]):
    name = "nas"

    def __init__(self, cfg: OmvConfig) -> None:
        super().__init__(cfg.poll_interval_seconds)
        self._cfg = cfg
        # Cliente propio: su cookie jar guarda la sesión de OMV.
        self._client = httpx.AsyncClient(base_url=cfg.url.rstrip("/"), timeout=15)
        self._logged_in = False
        # La CPU de OMV es instantánea y muy variable (incluye el pico de la propia
        # consulta): se muestra la media de las últimas lecturas.
        self._cpu_samples: deque[float] = deque(maxlen=CPU_SMOOTHING_SAMPLES)

    async def close(self) -> None:
        await self._client.aclose()

    async def _rpc(self, service: str, method: str, params: dict[str, Any] | None = None) -> Any:
        response = await self._client.post(
            "/rpc.php",
            json={"service": service, "method": method, "params": params or {}, "options": None},
        )
        try:
            body = response.json()
        except ValueError:
            response.raise_for_status()
            raise
        error = body.get("error") if isinstance(body, dict) else None
        if error:
            raise OmvRpcError(error.get("code"), error.get("message", "error RPC"))
        if response.status_code == 401:
            raise OmvRpcError(5001, "No autenticado")
        response.raise_for_status()
        return body.get("response")

    async def _login(self) -> None:
        password = require_secret(self._cfg.password, "omv.password")
        self._client.cookies.clear()
        try:
            result = await self._rpc("Session", "login", {"username": self._cfg.username, "password": password})
        except OmvRpcError as exc:
            # OMV responde a un login fallido con code 0 "Incorrect username or password".
            raise CredentialsError(f"OMV rechazó el login: {exc}") from exc
        if isinstance(result, dict) and result.get("authenticated") is False:
            raise CredentialsError("OMV rechazó el login")
        self._logged_in = True

    async def _call(self, service: str, method: str, params: dict[str, Any] | None = None) -> Any:
        if not self._logged_in:
            await self._login()
        try:
            return await self._rpc(service, method, params)
        except OmvRpcError as exc:
            if not exc.is_auth_error:
                raise
            self._logged_in = False
            await self._login()
            return await self._rpc(service, method, params)

    async def fetch(self) -> NasStatus:
        info = await self._call("System", "getInformation")
        filesystems = await self._call("FileSystemMgmt", "getList", {"start": 0, "limit": -1})

        cpu, memory, hostname, uptime = parse_system_info(info)
        self._cpu_samples.append(cpu.usage_percent)
        cpu = NasCpu(usage_percent=round(sum(self._cpu_samples) / len(self._cpu_samples), 1))
        storage = parse_filesystems(filesystems, self._cfg.exclude_mount_points)
        degraded = memory.percent >= DEGRADED_MEMORY_PERCENT or any(
            v.percent >= DEGRADED_STORAGE_PERCENT for v in storage
        )
        return NasStatus(
            status="degraded" if degraded else "healthy",
            fetched_at=utcnow(),
            hostname=hostname,
            uptime_seconds=uptime,
            cpu=cpu,
            memory=memory,
            storage=storage,
        )
