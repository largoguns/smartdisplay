import { useEffect, useState } from 'react';
import { Tv } from 'lucide-react';
import { isStale, usePolling } from '../hooks/usePolling';
import type { AnimeData } from '../types/dashboard';
import { StaleBadge } from './Card';

const ROTATE_SECONDS = 8;

/** Franja condicional: solo aparece si alguna serie tiene capítulos nuevos. */
export function AnimeTicker({ className = '' }: { className?: string }) {
  const state = usePolling<AnimeData>('/api/anime', 30 * 60_000);
  const items = state.data?.items ?? [];
  const [index, setIndex] = useState(0);

  useEffect(() => {
    if (items.length < 2) return;
    const timer = window.setInterval(() => setIndex((i) => i + 1), ROTATE_SECONDS * 1000);
    return () => window.clearInterval(timer);
  }, [items.length]);

  if (items.length === 0) return null;
  const item = items[index % items.length];

  return (
    <section
      className={`flex h-20 items-center gap-6 overflow-hidden rounded-3xl border border-white/[0.06] bg-slate-900/50 px-6 shadow-2xl shadow-black/40 backdrop-blur-xl ${className}`}
    >
      <span className="flex shrink-0 items-center gap-3 text-base font-semibold uppercase tracking-[0.2em] text-slate-400">
        <Tv className="h-6 w-6 text-violet-300" />
        Anime
      </span>
      <div key={item.id} className="flex min-w-0 flex-1 animate-fade-in items-center gap-4">
        {item.thumbnail_url && <img src={item.thumbnail_url} alt="" className="h-14 w-10 shrink-0 rounded-md object-cover" />}
        <span className="truncate text-2xl font-semibold tracking-tight text-white">{item.title}</span>
        <span className="shrink-0 rounded-lg bg-violet-400/15 px-3 py-1 text-lg font-bold text-violet-200">
          {item.new_count === 1 ? '1 capítulo nuevo' : `${item.new_count} capítulos nuevos`}
        </span>
      </div>
      {isStale(state) && <StaleBadge />}
      {items.length > 1 && (
        <span className="shrink-0 text-lg font-medium tabular-nums text-slate-500">
          {(index % items.length) + 1}/{items.length}
        </span>
      )}
    </section>
  );
}
