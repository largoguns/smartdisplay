import { useEffect, useRef } from 'react';
import { Music2, Speaker } from 'lucide-react';
import { useNow } from '../hooks/useNow';
import { usePolling } from '../hooks/usePolling';
import { formatDuration } from '../lib/format';
import type { NowPlaying, Track } from '../types/dashboard';

/** Máximo que se extrapola el progreso entre lecturas (evita derivas). */
const MAX_EXTRAPOLATION_MS = 15_000;

/**
 * Tarjeta condicional: sin reproducción activa colapsa a altura 0 para dar el
 * espacio a la tarjeta del tiempo.
 */
export function SpotifyNowPlaying() {
  const state = usePolling<NowPlaying>('/api/media/now-playing', 3_000);
  const now = useNow();
  const data = state.data;
  const active = state.error === null && data?.is_active === true && data.track !== null;

  // Se conserva la última pista para que no desaparezca durante el colapso.
  const last = useRef<{ track: Track; account: string | null; fetchedAt: number } | null>(null);
  useEffect(() => {
    if (active && data?.track) {
      last.current = { track: data.track, account: data.account, fetchedAt: Date.parse(data.fetched_at) };
    }
  }, [active, data]);
  const shown = active && data?.track ? { track: data.track, account: data.account, fetchedAt: Date.parse(data.fetched_at) } : last.current;

  let progress = 0;
  if (shown) {
    const elapsed = active ? Math.min(Math.max(now.getTime() - shown.fetchedAt, 0), MAX_EXTRAPOLATION_MS) : 0;
    progress = Math.min(shown.track.progress_ms + elapsed, shown.track.duration_ms);
  }
  const percent = shown && shown.track.duration_ms > 0 ? (progress / shown.track.duration_ms) * 100 : 0;

  return (
    <div
      aria-hidden={!active}
      className={`shrink-0 overflow-hidden transition-all duration-700 ease-in-out ${
        active ? 'max-h-[20rem] opacity-100' : '-mt-4 max-h-0 opacity-0'
      }`}
    >
      {shown && (
        <section className="relative overflow-hidden rounded-3xl border border-white/[0.06] bg-slate-900/60 p-5 shadow-2xl shadow-black/40 backdrop-blur-xl">
          {shown.track.album_art_url && (
            <img src={shown.track.album_art_url} alt="" className="absolute inset-0 h-full w-full scale-150 object-cover opacity-25 blur-3xl" />
          )}
          <div className="relative flex items-center gap-6">
            {shown.track.album_art_url ? (
              <img src={shown.track.album_art_url} alt="" className="h-40 w-40 shrink-0 rounded-2xl object-cover shadow-xl shadow-black/50" />
            ) : (
              <div className="flex h-40 w-40 shrink-0 items-center justify-center rounded-2xl bg-slate-800">
                <Music2 className="h-16 w-16 text-slate-500" />
              </div>
            )}
            <div className="min-w-0 flex-1 space-y-2">
              <div className="line-clamp-2 text-3xl font-bold leading-tight tracking-tight text-white">{shown.track.title}</div>
              <div className="truncate text-xl font-medium text-slate-300">{shown.track.artist}</div>
              <div className="flex items-center gap-2 truncate text-base font-medium text-emerald-300">
                <Speaker className="h-5 w-5 shrink-0" />
                <span className="truncate">
                  {shown.track.device_name ?? 'Spotify'}
                  {shown.account && <span className="text-slate-400"> · {shown.account}</span>}
                </span>
              </div>
              <div className="flex items-center gap-3 pt-1">
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-white/10">
                  <div className="h-full rounded-full bg-emerald-400 transition-[width] duration-1000 ease-linear" style={{ width: `${percent}%` }} />
                </div>
                <span className="text-base font-semibold tabular-nums text-slate-300">
                  {formatDuration(progress)} / {formatDuration(shown.track.duration_ms)}
                </span>
              </div>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
