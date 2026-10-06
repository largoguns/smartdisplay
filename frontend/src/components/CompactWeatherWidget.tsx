import { isStale, usePolling } from '../hooks/usePolling';
import { weatherInfo } from '../lib/weather';
import type { WeatherData } from '../types/dashboard';
import { StaleBadge } from './Card';
import { LocationTag, dayName } from './WeatherWidget';

const NEXT_DAYS = 3;

/** Tarjeta compacta para ubicaciones secundarias: ahora, hoy y 3 días. */
export function CompactWeatherWidget({ index }: { index: number }) {
  const state = usePolling<WeatherData>(`/api/weather/${index}`, 5 * 60_000);
  const data = state.data;
  if (!data) return null;

  const now = weatherInfo(data.current.weather_code, data.current.is_day);
  const [today, ...rest] = data.daily;

  return (
    <section className="shrink-0 rounded-3xl border border-white/[0.06] bg-slate-900/50 px-6 py-4 shadow-2xl shadow-black/40 backdrop-blur-xl">
      <div className="flex items-center gap-4">
        <now.Icon className={`h-14 w-14 shrink-0 ${now.color}`} strokeWidth={1.75} />
        <span className="text-5xl font-bold tabular-nums tracking-tighter text-white">{Math.round(data.current.temperature)}°</span>
        <div className="min-w-0 flex-1">
          <LocationTag name={data.location} />
          <div className="truncate text-lg text-slate-400">{now.label}</div>
        </div>
        {isStale(state) ? (
          <StaleBadge />
        ) : (
          today && (
            <div className="text-right text-xl font-semibold tabular-nums">
              <span className="text-white">{Math.round(today.temperature_max)}°</span>
              <span className="ml-2 text-slate-500">{Math.round(today.temperature_min)}°</span>
            </div>
          )
        )}
      </div>
      <div className="mt-3 grid grid-cols-3 gap-2 border-t border-white/[0.06] pt-3">
        {rest.slice(0, NEXT_DAYS).map((day) => {
          const info = weatherInfo(day.weather_code);
          return (
            <div key={day.date} className="flex items-center justify-center gap-2 text-lg">
              <span className="font-semibold text-slate-400">{dayName(day.date)}</span>
              <info.Icon className={`h-6 w-6 ${info.color}`} />
              <span className="font-bold tabular-nums text-white">{Math.round(day.temperature_max)}°</span>
              <span className="tabular-nums text-slate-500">{Math.round(day.temperature_min)}°</span>
            </div>
          );
        })}
      </div>
    </section>
  );
}
