from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import CalendarSource, NewsFeed
from app.modules.base import PollingModule, utcnow
from app.modules.calendar import parse_ics
from app.modules.nas import parse_filesystems, parse_system_info
from app.modules.news import parse_feed
from app.modules.solar import parse_runtime_data
from app.modules.spotify import PlayerState, parse_player, select_playback
from app.modules.weather import parse_forecast
from app.schemas.models import AdguardStats, Track

TZ = ZoneInfo("Europe/Madrid")


def test_solar_parses_et_family() -> None:
    data = parse_runtime_data(
        {"ppv": 3400, "house_consumption": 850, "active_power": 2550, "pbattery1": 0, "battery_soc": 80, "e_day": 16.4}
    )
    assert data.ppv == 3400
    assert data.active_power == 2550
    assert data.battery_soc == 80
    assert data.today_energy_kwh == 16.4


def test_solar_dt_without_meter_reports_unknown_grid() -> None:
    # Lectura real de un GW3000D-NS sin medidor.
    data = parse_runtime_data(
        {"ppv": 588, "house_consumption": 589, "meter_active_power": -1, "meter_comm_status": 0, "e_day": 0.6}
    )
    assert data.ppv == 588
    assert data.active_power is None
    assert data.house_consumption is None


def test_solar_dt_with_meter_uses_meter() -> None:
    data = parse_runtime_data({"ppv": 2000, "house_consumption": 500, "meter_active_power": 1500, "meter_comm_status": 1})
    assert data.active_power == 1500
    assert data.house_consumption == 500


def test_solar_derives_missing_values() -> None:
    data = parse_runtime_data({"ppv1": 1000, "ppv2": 500, "active_power": -200, "e_day": 3})
    assert data.ppv == 1500
    assert data.house_consumption == 1700  # 1500 FV + 200 importados
    assert data.battery_power is None


ICS = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//test//EN
BEGIN:VEVENT
UID:weekly
DTSTART;TZID=Europe/Madrid:20261001T093000
DTEND;TZID=Europe/Madrid:20261001T103000
RRULE:FREQ=DAILY;COUNT=30
SUMMARY:Reunion equipo
END:VEVENT
BEGIN:VEVENT
UID:allday
DTSTART;VALUE=DATE:20261007
DTEND;VALUE=DATE:20261008
SUMMARY:Cumple
END:VEVENT
BEGIN:VEVENT
UID:cancelled
DTSTART:20261006T120000Z
DTEND:20261006T130000Z
STATUS:CANCELLED
SUMMARY:Cancelado
END:VEVENT
END:VCALENDAR
"""


def test_calendar_expands_recurrences_and_all_day() -> None:
    start = datetime(2026, 10, 6, tzinfo=TZ)
    end = datetime(2026, 10, 13, 23, 59, 59, tzinfo=TZ)
    events = parse_ics(ICS, CalendarSource(name="P", ics_url="x"), start, end, TZ)
    titles = [e.title for e in events]
    assert titles.count("Reunion equipo") == 8
    assert "Cancelado" not in titles
    cumple = next(e for e in events if e.title == "Cumple")
    assert cumple.is_all_day
    assert cumple.start == datetime(2026, 10, 7, tzinfo=TZ)
    assert cumple.end == datetime(2026, 10, 8, tzinfo=TZ)
    meeting = next(e for e in events if e.title == "Reunion equipo")
    assert meeting.to_model(datetime(2026, 10, 6, 10, 0, tzinfo=TZ)).is_ongoing


def test_weather_parses_open_meteo_payload() -> None:
    hours = [f"2026-10-06T{h:02d}:00" for h in range(24)]
    days = [f"2026-10-{d:02d}" for d in range(6, 12)]
    payload = {
        "timezone": "Europe/Madrid",
        "current": {
            "time": "2026-10-06T08:30",
            "temperature_2m": 19.2,
            "apparent_temperature": 18.7,
            "relative_humidity_2m": 60,
            "wind_speed_10m": 7.5,
            "weather_code": 2,
            "is_day": 1,
        },
        "hourly": {
            "time": hours,
            "temperature_2m": [15.0] * 24,
            "weather_code": [1] * 24,
            "precipitation_probability": [None] + [10] * 23,
            "is_day": [0] * 8 + [1] * 12 + [0] * 4,
        },
        "daily": {
            "time": days,
            "temperature_2m_min": [10.0] * 6,
            "temperature_2m_max": [22.0] * 6,
            "weather_code": [3] * 6,
            "precipitation_probability_max": [20] * 6,
            "sunrise": ["2026-10-06T08:05"] * 6,
            "sunset": ["2026-10-06T19:40"] * 6,
        },
    }
    data = parse_forecast(payload, "Madrid")
    assert data.location == "Madrid"
    assert data.current.is_day is True
    assert len(data.hourly) == 12
    assert data.hourly[0].time.hour == 9
    assert len(data.daily) == 5


def _state(account: str, device: str, playing: bool = True) -> PlayerState:
    track = Track(
        title="t", artist="a", album="b", album_art_url=None, duration_ms=1, progress_ms=0, device_name=device
    )
    return PlayerState(account=account, is_playing=playing, track=track)


def test_spotify_selection_rules() -> None:
    preferred = ["Google Home Cocina", "Google Home Salon"]
    phone = _state("Cuenta 1", "iPhone")
    kitchen = _state("Cuenta 2", "google home cocina")
    assert select_playback([None, None], preferred) is None
    assert select_playback([_state("Cuenta 1", "x", playing=False), None], preferred) is None
    assert select_playback([phone, None], preferred) is phone
    assert select_playback([phone, kitchen], preferred) is kitchen
    assert select_playback([_state("Cuenta 1", "Google Home Salon"), kitchen], preferred) is kitchen


def test_spotify_parses_player_payload() -> None:
    state = parse_player(
        "Cuenta 1",
        {
            "is_playing": True,
            "progress_ms": 45000,
            "device": {"name": "Google Home Cocina"},
            "item": {
                "type": "track",
                "name": "Song",
                "duration_ms": 210000,
                "artists": [{"name": "A"}, {"name": "B"}],
                "album": {"name": "Album", "images": [{"url": "big"}, {"url": "small"}]},
            },
        },
    )
    assert state.is_playing
    assert state.track is not None
    assert state.track.artist == "A, B"
    assert state.track.album_art_url == "big"


def test_nas_parsers() -> None:
    cpu, memory, hostname, uptime = parse_system_info(
        {"cpuUsage": 18.47, "memTotal": str(16 * 1024**3), "memAvailable": 11 * 1024**3, "uptime": 3600.5, "hostname": "nas"}
    )
    assert cpu.usage_percent == 18.5
    assert memory.used_gb == 5.0
    assert uptime == 3600 and hostname == "nas"

    volumes = parse_filesystems(
        {
            "total": 3,
            "data": [
                {"mounted": True, "mountpoint": "/", "size": "100", "available": "50"},
                {"mounted": False, "mountpoint": "/srv/x", "size": "100", "available": "50"},
                {
                    "mounted": True,
                    "mountpoint": "/srv/dev-disk-by-uuid-data",
                    "label": "Data Pool",
                    "size": str(8000 * 1024**3),
                    "available": str(3900 * 1024**3),
                    "percentage": 51,
                },
            ],
        },
        exclude=["/"],
    )
    assert [v.label for v in volumes] == ["Data Pool"]
    assert volumes[0].used_gb == 4100.0


def test_news_parses_rss() -> None:
    rss = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>X</title>
    <item><title>Nuevo &amp; avance</title><link>https://x/1</link><pubDate>Tue, 06 Oct 2026 08:00:00 GMT</pubDate></item>
    </channel></rss>"""
    items = parse_feed(rss, NewsFeed(name="Xataka", url="x"))
    assert items[0].title == "Nuevo & avance"
    assert items[0].published_at == datetime(2026, 10, 6, 8, tzinfo=timezone.utc)


class _FlakyModule(PollingModule[AdguardStats]):
    name = "adguard"

    def __init__(self) -> None:
        super().__init__(60)
        self.fail = False

    async def fetch(self) -> AdguardStats:
        if self.fail:
            raise ConnectionError("down")
        return AdguardStats(
            fetched_at=utcnow(), protection_enabled=True, queries_24h=100, blocked_24h=15, block_ratio_percent=15.0
        )


def test_api_serves_stale_data_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    from app import main

    module = _FlakyModule()
    monkeypatch.setattr(main, "build_modules", lambda cfg, client: {"adguard": module})
    monkeypatch.setattr(main, "get_config", lambda: main.AppConfig())
    monkeypatch.setattr(module, "start", lambda: None)

    with TestClient(main.app) as client:
        assert client.get("/api/network/adguard").status_code == 503
        assert client.get("/api/weather").status_code == 404
        assert client.get("/api/weather/locations").json() == []

        asyncio.run(module.refresh())
        ok = client.get("/api/network/adguard").json()
        assert ok["status"] == "ok" and ok["block_ratio_percent"] == 15.0

        module.fail = True
        assert asyncio.run(module.refresh()) == module.retry
        stale = client.get("/api/network/adguard").json()
        assert stale["status"] == "stale" and stale["queries_24h"] == 100
        assert client.get("/api/health").json()["modules"]["adguard"]["last_error"] == "ConnectionError: down"


def test_weather_config_accepts_multiple_locations() -> None:
    from app.config import WeatherConfig

    with pytest.raises(ValueError):
        WeatherConfig.model_validate({"locations": []})  # al menos una ubicación

    multi = WeatherConfig.model_validate(
        {"locations": [{"name": "Casa", "latitude": 37.5, "longitude": -6.1}, {"name": "Madrid", "latitude": 40.4, "longitude": -3.7}]}
    )
    assert [l.name for l in multi.locations] == ["Casa", "Madrid"]


def test_serves_spa_and_keeps_api_404(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    from app import main

    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html>spa</html>")
    (tmp_path / "assets" / "app-1234.js").write_text("console.log(1)")
    (tmp_path.parent / "secret.txt").write_text("no")
    monkeypatch.setattr(main, "STATIC_DIR", tmp_path)
    monkeypatch.setattr(main, "build_modules", lambda cfg, client: {})
    monkeypatch.setattr(main, "get_config", lambda: main.AppConfig())

    with TestClient(main.app) as client:
        index = client.get("/")
        assert index.text == "<html>spa</html>" and index.headers["cache-control"] == "no-store"
        asset = client.get("/assets/app-1234.js")
        assert asset.text == "console.log(1)" and "immutable" in asset.headers["cache-control"]
        assert client.get("/cualquier/ruta").text == "<html>spa</html>"
        assert client.get("/../secret.txt").text != "no"
        assert client.get("/api/no-existe").status_code == 404


# ── SEMS ─────────────────────────────────────────────────────────────────────


def test_sems_signature_matches_web_client() -> None:
    from app.modules.sems import sign

    # Formato verificado contra peticiones reales de semsplus.goodwe.com:
    # base64(sha256("ts@uid@token") + "@ts"). Valores ficticios.
    expected = "NzYzNTRmOWRkMjZkYTY3MmUyOGJlYjNjYjM3YjU4YWM5YWZlMjIwN2MyMzU0NThiNGYxZDdiY2Y3NGZlNTUxZUAxNzkxMjc5MDg1MTky"
    assert sign("00000000-0000-4000-8000-000000000000", "0123456789abcdef0123456789abcdef", 1791279085192) == expected
    assert base64.b64decode(expected).decode().endswith("@1791279085192")


def test_sems_flow_direction() -> None:
    from app.modules.sems import parse_flow

    base = {"pSystem": 0.588, "pConsum": 0.37, "pGrid": 0.218, "refreshTime": "2026-10-06T11:33:00"}
    exporting = parse_flow({**base, "flows": {"pSystem": ["pConsum", "pGrid"]}}, TZ)
    assert (exporting.pv_w, exporting.house_w, exporting.grid_w) == (588.0, 370.0, 218.0)
    assert exporting.refreshed_at == datetime(2026, 10, 6, 11, 33, tzinfo=TZ)

    night = parse_flow({"pSystem": 0, "pConsum": 0.4, "pGrid": 0.4, "flows": {"pGrid": ["pConsum"]}}, TZ)
    assert night.grid_w == -400.0

    # Respuesta real de SEMS: al importar, pGrid ya viene en negativo.
    signed = parse_flow(
        {"pSystem": 0.002, "pConsum": 0.393, "pGrid": -0.391, "flows": {"pSystem": ["pConsum"], "pGrid": ["pConsum"]}}, TZ
    )
    assert signed.grid_w == -391.0

    idle = parse_flow({"pSystem": 0.3, "pConsum": 0.3, "pGrid": 0, "flows": {"pSystem": ["pConsum"]}}, TZ)
    assert idle.grid_w == 0.0


def test_sems_day_summary() -> None:
    from datetime import date

    from app.modules.sems import parse_day

    production = {"proSystemTotalStats": 9.82, "proGridStats": 4.97, "proPurchaseStats": 6.86, "proConsumStats": 11.71, "currency": "EUR"}
    curve = {
        "dataList": [
            {"item": "pSystem", "unit": "kW", "powerData": [
                {"tp": "2026-10-07 00:00:00", "power": -0.004},
                {"tp": "2026-10-07 00:01:00", "power": 0.002},
                {"tp": "2026-10-07 13:05:00", "power": 2.0},
                {"tp": "2026-10-07 13:06:00", "power": 2.6},
                {"tp": "2026-10-07 13:10:00", "power": None},
            ]},
            {"item": "pConsum", "unit": "kW", "powerData": [
                {"tp": "2026-10-07 00:00:00", "power": 0.2},
                {"tp": "2026-10-07 13:05:00", "power": 0.4},
            ]},
            {"item": "pGrid", "unit": "kW", "powerData": [{"tp": "2026-10-07 13:05:00", "power": 1.6}]},
        ]
    }
    day = parse_day(date(2026, 10, 7), production, curve)
    assert (day.generated_kwh, day.consumed_kwh, day.imported_kwh, day.exported_kwh) == (9.82, 11.71, 6.86, 4.97)
    assert [(p.minute, p.pv_w, p.house_w) for p in day.points] == [(0, 0.0, 200.0), (785, 2300.0, 400.0)]

    empty = parse_day(date(2026, 10, 7), {}, {})
    assert empty.imported_kwh is None and empty.points == []


def test_solar_merges_inverter_with_sems() -> None:
    from app.modules.solar import merge_with_sems
    from app.schemas.models import SemsFlow

    cloud = SemsFlow(fetched_at=utcnow(), pv_w=538.0, house_w=254.0, grid_w=284.0, refreshed_at=datetime(2026, 10, 6, 11, 46, tzinfo=TZ))
    no_meter = parse_runtime_data({"ppv": 553, "meter_comm_status": 0, "e_day": 0.6})

    # Balance: hogar de SEMS y red recalculada con la FV en vivo (553 − 254).
    merged = merge_with_sems(no_meter, cloud, 0.0)
    assert merged is not None
    assert (merged.ppv, merged.house_consumption, merged.active_power) == (553, 254.0, 299.0)
    assert merged.flow_source == "balance" and merged.today_energy_kwh == 0.6

    # Una nube: la FV cae por debajo del consumo y la red pasa a importar.
    cloudy = merge_with_sems(parse_runtime_data({"ppv": 100, "meter_comm_status": 0}), cloud, 0.0)
    assert cloudy is not None and cloudy.active_power == -154.0

    # Inversor apagado (noche): solo SEMS, conservando la energía del día.
    night = merge_with_sems(None, cloud, 12.3)
    assert night is not None and night.flow_source == "sems"
    assert (night.ppv, night.active_power, night.today_energy_kwh) == (538.0, 284.0, 12.3)

    # Con medidor propio manda el inversor.
    metered = parse_runtime_data({"ppv": 2000, "active_power": 1500, "house_consumption": 500})
    assert merge_with_sems(metered, cloud, 0.0).flow_source == "inverter"

    assert merge_with_sems(None, None, 0.0) is None
    assert merge_with_sems(no_meter, None, 0.0).flow_source is None


def test_sems_config_accepts_hash_or_password() -> None:
    from app.config import SemsConfig
    from app.modules.sems import hash_password

    assert SemsConfig(username="u", station_id="s", password_hash="abc").password_hash == "abc"
    assert SemsConfig(username="u", station_id="s", password="x").password == "x"
    with pytest.raises(ValueError):
        SemsConfig(username="u", station_id="s")
    # Mismo formato que envía la web: base64 del md5 en hexadecimal.
    assert hash_password("secreto") == "ZTIwMTk5NGRjYTkzMjBmYzk0MzM2NjAzYjFjZmM5NzA="


def test_config_expands_env_references(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import expand_env

    monkeypatch.setenv("OMV_PASSWORD", "s3cr3t")
    monkeypatch.delenv("ADGUARD_PASSWORD", raising=False)
    missing: set[str] = set()
    raw = {"omv": {"password": "${OMV_PASSWORD}"}, "adguard": {"password": "${ADGUARD_PASSWORD}"}, "x": ["a-${OMV_PASSWORD}", 3, "$literal"]}
    assert expand_env(raw, missing) == {"omv": {"password": "s3cr3t"}, "adguard": {"password": ""}, "x": ["a-s3cr3t", 3, "$literal"]}
    assert missing == {"ADGUARD_PASSWORD"}


def test_credentials_errors_wait_long_and_skip_empty_secrets() -> None:
    from app.config import AdguardConfig, OmvConfig
    from app.modules.adguard import AdguardModule
    from app.modules.base import AUTH_RETRY_SECONDS
    from app.modules.nas import NasModule

    calls: list[str] = []

    def handler(request):  # cualquier petición a la red sería un intento de login
        calls.append(str(request.url))
        raise AssertionError("no debe contactar con el servicio con la contraseña vacía")

    async def run() -> None:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        adguard = AdguardModule(AdguardConfig(url="http://x", username="u", password=""), client)
        nas = NasModule(OmvConfig(url="http://x", username="admin", password=""))
        nas._client = client
        for module in (adguard, nas):
            assert await module.refresh() == AUTH_RETRY_SECONDS
            assert "vacío" in (module.health().last_error or "")
        await client.aclose()

    asyncio.run(run())
    assert calls == []


def test_rejected_login_waits_long() -> None:
    from app.config import OmvConfig
    from app.modules.base import AUTH_RETRY_SECONDS
    from app.modules.nas import NasModule

    attempts = 0

    def handler(request):
        nonlocal attempts
        attempts += 1
        return httpx.Response(200, json={"response": None, "error": {"code": 0, "message": "Incorrect username or password."}})

    async def run() -> None:
        nas = NasModule(OmvConfig(url="http://x", username="admin", password="mala"))
        nas._client = httpx.AsyncClient(base_url="http://x", transport=httpx.MockTransport(handler))
        assert await nas.refresh() == AUTH_RETRY_SECONDS
        await nas._client.aclose()

    asyncio.run(run())
    assert attempts == 1  # un único intento, sin reintento inmediato


def test_nas_volume_label_is_readable() -> None:
    from app.modules.nas import _volume_label

    assert _volume_label({"label": "Data Pool"}, "/srv/x") == "Data Pool"
    assert _volume_label({"label": "", "description": "/dev/sdb1 [EXT4, 514.12 GiB (57%) used]", "devicefile": "/dev/disk/by-uuid/2a6b"}, "/srv/x") == "/dev/sdb1"
    assert _volume_label({}, "/srv/mergerfs/storage") == "/srv/mergerfs/storage"


def test_nas_cpu_reads_omv8_field() -> None:
    cpu, *_ = parse_system_info({"cpuUtilization": 8.04, "memTotal": 1, "memAvailable": 1})
    assert cpu.usage_percent == 8.0
    cpu, *_ = parse_system_info({"cpuUsage": 12.0, "memTotal": 1})  # OMV <= 7
    assert cpu.usage_percent == 12.0
