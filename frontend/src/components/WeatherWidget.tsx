import { CloudSun, Droplets, MapPin, Umbrella, Wind } from 'lucide-react';
import { useElementHeight } from '../hooks/useElementHeight';
import { isStale, usePolling } from '../hooks/usePolling';
import { capitalize, formatNumber, parseLocalDate, startOfDay } from '../lib/format';
import { airQualityLevel, uvLevel, weatherInfo } from '../lib/weather';
import type { DailyForecast, WeatherData } from '../types/dashboard';
import { Card, Placeholder, UpdatedAgo } from './Card';

const HOURS_SHOWN = 6;
/** Solo se muestra la probabilidad de lluvia cuando es relevante. */
const RAIN_MIN_PERCENT = 20;

export function dayName(isoDate: string): string {
  const date = parseLocalDate(isoDate);
  if (date.getTime() === startOfDay(new Date()).getTime()) return 'Hoy';
  return capitalize(date.toLocaleDateString('es-ES', { weekday: 'short' }).replace('.', ''));
}

/** Columnas de la previsión diaria: día, icono, mín, máx, sensación, lluvia, viento. */
const DAILY_GRID = 'grid grid-cols-[4rem_2rem_repeat(5,minmax(0,1fr))] items-center gap-x-3';

function DailyHeader() {
  return (
    <div className={`${DAILY_GRID} text-center text-sm font-semibold uppercase tracking-wider text-slate-500`}>
      <span className="col-start-3">Mín</span>
      <span>Máx</span>
      <span>Sensación</span>
      <span>Lluvia</span>
      <span>Viento</span>
    </div>
  );
}

function DailyRow({ day }: { day: DailyForecast }) {
  const { Icon, color } = weatherInfo(day.weather_code);
  const feelsMin = day.apparent_temperature_min;
  const feelsMax = day.apparent_temperature_max;

  return (
    <li className={`${DAILY_GRID} text-center tabular-nums`}>
      <span className="text-left text-2xl font-semibold text-slate-300">{dayName(day.date)}</span>
      <Icon className={`h-8 w-8 ${color}`} />
      <span className="text-2xl font-semibold text-sky-300">{Math.round(day.temperature_min)}°</span>
      <span className="text-2xl font-bold text-orange-300">{Math.round(day.temperature_max)}°</span>
      <span className="text-xl font-semibold text-slate-300">
        {feelsMin !== null && feelsMax !== null ? `${Math.round(feelsMin)}° / ${Math.round(feelsMax)}°` : '–'}
      </span>
      <span className={`text-xl font-semibold ${(day.precipitation_probability_max ?? 0) >= RAIN_MIN_PERCENT ? 'text-sky-300' : 'text-slate-500'}`}>
        {day.precipitation_probability_max !== null ? `${day.precipitation_probability_max}%` : '–'}
      </span>
      <span className="text-xl font-semibold text-slate-300">
        {day.wind_speed_max !== null ? (
          <>
            {Math.round(day.wind_speed_max)}
            <span className="ml-1 text-base font-medium text-slate-500">km/h</span>
          </>
        ) : (
          '–'
        )}
      </span>
    </li>
  );
}

// Altos aproximados de cada bloque, en rem (la interfaz escala con la pantalla),
// para decidir qué cabe en la tarjeta.
const CURRENT_H = 8.75;
const HOURLY_H = 9.375;
const DAY_ROW_H = 2.625;
const DAILY_HEADER_H = 1.75;
const GAP_H = 1.25;
const FULL_H = CURRENT_H + GAP_H + HOURLY_H + GAP_H + DAILY_HEADER_H + 5 * DAY_ROW_H;

function rootFontPx(): number {
  return parseFloat(getComputedStyle(document.documentElement).fontSize) || 16;
}

export function LocationTag({ name }: { name: string }) {
  return (
    <span className="flex items-center gap-1.5 text-xl font-semibold text-slate-200">
      <MapPin className="h-5 w-5 text-slate-400" />
      {name}
    </span>
  );
}

/** Widget completo de la ubicación principal; se adapta al alto disponible. */
export function WeatherWidget({ index = 0, className = '' }: { index?: number; className?: string }) {
  const state = usePolling<WeatherData>(`/api/weather/${index}`, 5 * 60_000);
  const [ref, heightPx] = useElementHeight<HTMLDivElement>();
  const height = heightPx / rootFontPx(); // en rem
  const data = state.data;

  // Sin medida todavía (height 0) se asume que cabe todo.
  const showHourly = height === 0 || height >= FULL_H;
  const available = height - CURRENT_H - GAP_H - DAILY_HEADER_H - (showHourly ? HOURLY_H + GAP_H : 0);
  const daysShown = height === 0 ? 5 : Math.max(2, Math.min(5, Math.floor(available / DAY_ROW_H)));

  return (
    <Card
      title="El tiempo"
      icon={CloudSun}
      accent="text-amber-300"
      stale={data ? isStale(state) : false}
      headerRight={
        data && (
          <>
            <UpdatedAgo at={data.fetched_at} />
            <LocationTag name={data.location} />
          </>
        )
      }
      className={className}
    >
      {/* absolute: el alto medido es el disponible, no el del contenido. */}
      <div ref={ref} className="absolute inset-0">
        {data ? <WeatherBody data={data} showHourly={showHourly} daysShown={daysShown} /> : <Placeholder>Cargando previsión…</Placeholder>}
      </div>
    </Card>
  );
}

/** Índice UV máximo de hoy y calidad del aire actual, con su categoría. */
function IndexesRow({ uv, aqi }: { uv: number | null; aqi: number | null }) {
  if (uv === null && aqi === null) return null;
  const uvInfo = uv !== null ? uvLevel(uv) : null;
  const air = aqi !== null ? airQualityLevel(aqi) : null;
  return (
    <div className="flex gap-5 whitespace-nowrap text-xl text-slate-400">
      {uvInfo && uv !== null && (
        <span>
          UV <span className={`font-semibold ${uvInfo.color}`}>{Math.round(uv)} {uvInfo.label}</span>
        </span>
      )}
      {air && (
        <span>
          Aire <span className={`font-semibold ${air.color}`}>{air.label}</span>
        </span>
      )}
    </div>
  );
}

function WeatherBody({ data, showHourly, daysShown }: { data: WeatherData; showHourly: boolean; daysShown: number }) {
  const { current } = data;
  const now = weatherInfo(current.weather_code, current.is_day);
  const days = data.daily.slice(0, daysShown);
  // La previsión horaria puede haberse quedado atrás si el último fetch es antiguo.
  const hours = data.hourly.filter((h) => new Date(h.time).getTime() > Date.now() - 3_600_000).slice(0, HOURS_SHOWN);

  return (
    <div className="flex h-full flex-col justify-evenly gap-5">
      <div className="flex items-center gap-6">
        <now.Icon className={`h-28 w-28 shrink-0 ${now.color}`} strokeWidth={1.5} />
        <div className="text-8xl font-bold tabular-nums tracking-tighter text-white">{Math.round(current.temperature)}°</div>
        <div className="min-w-0 space-y-1.5">
          <div className="truncate text-2xl font-semibold text-slate-100">{now.label}</div>
          <div className="text-xl text-slate-400">
            Sensación <span className="font-semibold text-slate-200">{Math.round(current.apparent_temperature)}°</span>
          </div>
          <div className="flex gap-5 text-xl text-slate-400">
            <span className="flex items-center gap-1.5">
              <Droplets className="h-5 w-5 text-sky-400" />
              {formatNumber(current.humidity)}%
            </span>
            <span className="flex items-center gap-1.5">
              <Wind className="h-5 w-5 text-slate-300" />
              {formatNumber(current.wind_speed)} km/h
            </span>
          </div>
          <IndexesRow uv={data.daily[0]?.uv_index_max ?? null} aqi={current.european_aqi} />
        </div>
      </div>

      {showHourly && (
        <div className="grid grid-cols-6 gap-2 rounded-2xl bg-white/[0.03] p-3">
          {hours.map((hour) => {
            const info = weatherInfo(hour.weather_code, hour.is_day);
            const rain = hour.precipitation_probability ?? 0;
            return (
              <div key={hour.time} className="flex flex-col items-center gap-1">
                <span className="text-lg font-medium text-slate-400">{new Date(hour.time).getHours()}h</span>
                <info.Icon className={`h-8 w-8 ${info.color}`} />
                <span className="text-2xl font-bold tabular-nums">{Math.round(hour.temperature)}°</span>
                <span className="flex h-5 items-center gap-1 text-sm font-semibold text-sky-300">
                  {rain >= RAIN_MIN_PERCENT && (
                    <>
                      <Umbrella className="h-3.5 w-3.5" />
                      {rain}%
                    </>
                  )}
                </span>
              </div>
            );
          })}
        </div>
      )}

      <div className="space-y-1">
        <DailyHeader />
        <ul className="space-y-2.5">
          {days.map((day) => (
            <DailyRow key={day.date} day={day} />
          ))}
        </ul>
      </div>
    </div>
  );
}
