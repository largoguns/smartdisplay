import { useEffect } from 'react';
import { AnimeTicker } from './components/AnimeTicker';
import { CalendarWidget } from './components/CalendarWidget';
import { ClockWidget } from './components/ClockWidget';
import { KeepShoppingWidget } from './components/KeepShoppingWidget';
import { NewsTicker } from './components/NewsTicker';
import { SolarFlowWidget } from './components/SolarFlowWidget';
import { SpotifyNowPlaying } from './components/SpotifyNowPlaying';
import { SystemPills } from './components/SystemPills';
import { WeatherCarousel } from './components/WeatherCarousel';
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

/** Cada cuánto se comprueba si se ha desplegado una build nueva. */
const BUILD_CHECK_MS = 60_000;
const BUILD_SCRIPT = /\/assets\/index-[\w-]+\.js/;

/** Recarga en cuanto el index.html servido apunta a otro bundle (nuevo despliegue). */
function useReloadOnNewBuild() {
  useEffect(() => {
    const loaded = document.querySelector<HTMLScriptElement>('script[type="module"][src]')?.src.match(BUILD_SCRIPT)?.[0];
    if (!loaded) return; // servidor de desarrollo de Vite: no hay bundle con hash
    const timer = window.setInterval(async () => {
      try {
        const res = await fetch('/', { cache: 'no-store' });
        if (!res.ok) return;
        const served = (await res.text()).match(BUILD_SCRIPT)?.[0];
        // Sin bundle en la respuesta (backend a medio arrancar...) no se recarga.
        if (served && served !== loaded) window.location.reload();
      } catch {
        // Servidor caído durante el despliegue: se sigue mostrando lo que hay.
      }
    }, BUILD_CHECK_MS);
    return () => window.clearInterval(timer);
  }, []);
}

export default function App() {
  useDailyReload();
  useReloadOnNewBuild();
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
        <SolarFlowWidget className="flex-[3]" />
        <KeepShoppingWidget className="flex-[2]" />
      </div>

      <div className="col-span-4 flex min-h-0 flex-col gap-4">
        <WeatherWidget className="flex-1" />
        <WeatherCarousel indexes={secondary.map((l) => l.index)} />
        <SpotifyNowPlaying />
      </div>

      <div className="col-span-12 flex flex-col gap-4">
        <AnimeTicker />
        <NewsTicker />
      </div>
    </main>
  );
}
