import { CloudSun, Droplets, MapPin, Umbrella, Wind } from 'lucide-react';
import { useElementHeight } from '../hooks/useElementHeight';
import { isStale, usePolling } from '../hooks/usePolling';
import { capitalize, formatNumber, parseLocalDate, startOfDay } from '../lib/format';
import { weatherInfo } from '../lib/weather';
import type { DailyForecast, WeatherData } from '../types/dashboard';
import { Card, Placeholder } from './Card';

const HOURS_SHOWN = 6;
/** Solo se muestra la probabilidad de lluvia cuando es relevante. */
const RAIN_MIN_PERCENT = 20;

export function dayName(isoDate: string): string {
  const date = parseLocalDate(isoDate);
  if (date.getTime() === startOfDay(new Date()).getTime()) return 'Hoy';
  return capitalize(date.toLocaleDateString('es-ES', { weekday: 'short' }).replace('.', ''));
}

function DailyRow({ day, low, high }: { day: DailyForecast; low: number; high: number }) {
  const { Icon, color } = weatherInfo(day.weather_code);
  const span = Math.max(high - low, 1);
  const left = ((day.temperature_min - low) / span) * 100;
  const width = ((day.temperature_max - day.temperature_min) / span) * 100;
  const rain = day.precipitation_probability_max ?? 0;

  return (
    <li className="flex items-center gap-4">
      <span className="w-16 text-2xl font-semibold text-slate-300">{dayName(day.date)}</span>
      <Icon className={`h-8 w-8 shrink-0 ${color}`} />
      <span className="w-14 text-right text-lg font-semibold tabular-nums text-sky-300">
        {rain >= RAIN_MIN_PERCENT ? `${rain}%` : ''}
      </span>
      <span className="w-12 text-right text-2xl font-semibold tabular-nums text-slate-400">{Math.round(day.temperature_min)}°</span>
      <span className="relative h-2 flex-1 rounded-full bg-slate-800">
        <span
          className="absolute inset-y-0 rounded-full bg-gradient-to-r from-sky-400 via-amber-300 to-orange-400"
          style={{ left: `${left}%`, width: `${Math.max(width, 4)}%` }}
        />
      </span>
      <span className="w-12 text-2xl font-bold tabular-nums text-white">{Math.round(day.temperature_max)}°</span>
    </li>
  );
}

// Altos aproximados (px) de cada bloque para decidir qué cabe en la tarjeta.
const CURRENT_H = 112;
const HOURLY_H = 150;
const DAY_ROW_H = 42;
const GAP_H = 20;
const FULL_H = CURRENT_H + GAP_H + HOURLY_H + GAP_H + 5 * DAY_ROW_H;

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
  const [ref, height] = useElementHeight<HTMLDivElement>();
  const data = state.data;

  // Sin medida todavía (height 0) se asume que cabe todo.
  const showHourly = height === 0 || height >= FULL_H;
  const available = height - CURRENT_H - GAP_H - (showHourly ? HOURLY_H + GAP_H : 0);
  const daysShown = height === 0 ? 5 : Math.max(2, Math.min(5, Math.floor(available / DAY_ROW_H)));

  return (
    <Card
      title="El tiempo"
      icon={CloudSun}
      accent="text-amber-300"
      stale={data ? isStale(state) : false}
      headerRight={data && <LocationTag name={data.location} />}
      className={className}
    >
      {/* absolute: el alto medido es el disponible, no el del contenido. */}
      <div ref={ref} className="absolute inset-0">
        {data ? <WeatherBody data={data} showHourly={showHourly} daysShown={daysShown} /> : <Placeholder>Cargando previsión…</Placeholder>}
      </div>
    </Card>
  );
}

function WeatherBody({ data, showHourly, daysShown }: { data: WeatherData; showHourly: boolean; daysShown: number }) {
  const { current } = data;
  const now = weatherInfo(current.weather_code, current.is_day);
  const days = data.daily.slice(0, daysShown);
  const low = Math.min(...days.map((d) => d.temperature_min));
  const high = Math.max(...days.map((d) => d.temperature_max));
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

      <ul className="space-y-2.5">
        {days.map((day) => (
          <DailyRow key={day.date} day={day} low={low} high={high} />
        ))}
      </ul>
    </div>
  );
}
