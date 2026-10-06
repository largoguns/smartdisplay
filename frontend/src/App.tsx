import { useEffect } from 'react';
import { CalendarWidget } from './components/CalendarWidget';
import { CompactWeatherWidget } from './components/CompactWeatherWidget';
import { ClockWidget } from './components/ClockWidget';
import { KeepShoppingWidget } from './components/KeepShoppingWidget';
import { NewsTicker } from './components/NewsTicker';
import { SolarFlowWidget } from './components/SolarFlowWidget';
import { SpotifyNowPlaying } from './components/SpotifyNowPlaying';
import { SystemPills } from './components/SystemPills';
import { WeatherWidget } from './components/WeatherWidget';
import { usePolling } from './hooks/usePolling';
import type { WeatherLocationInfo } from './types/dashboard';

/** Hora de la recarga diaria: limpia fugas de memoria del kiosko y recoge nuevas builds. */
const DAILY_RELOAD_HOUR = 4;

function useDailyReload() {
  useEffect(() => {
    const next = new Date();
    next.setHours(DAILY_RELOAD_HOUR, 0, 0, 0);
    if (next.getTime() <= Date.now()) next.setDate(next.getDate() + 1);
    const timer = window.setTimeout(() => window.location.reload(), next.getTime() - Date.now());
    return () => window.clearTimeout(timer);
  }, []);
}

export default function App() {
  useDailyReload();
  const { data: locations } = usePolling<WeatherLocationInfo[]>('/api/weather/locations', 10 * 60_000);
  const secondary = locations?.filter((l) => l.index > 0) ?? [];

  return (
    <main className="grid h-screen w-screen cursor-none select-none grid-cols-12 grid-rows-[auto_minmax(0,1fr)_auto] gap-4 overflow-hidden bg-transparent p-4 text-slate-100">
      <header className="col-span-12 flex items-center justify-between px-2">
        <ClockWidget />
        <SystemPills />
      </header>

      <CalendarWidget className="col-span-4" />

      <div className="col-span-4 flex min-h-0 flex-col gap-4">
        <SolarFlowWidget className="flex-1" />
        <KeepShoppingWidget className="flex-1" />
      </div>

      <div className="col-span-4 flex min-h-0 flex-col gap-4">
        <WeatherWidget className="flex-1" />
        {secondary.map((location) => (
          <CompactWeatherWidget key={location.index} index={location.index} />
        ))}
        <SpotifyNowPlaying />
      </div>

      <NewsTicker className="col-span-12" />
    </main>
  );
}
