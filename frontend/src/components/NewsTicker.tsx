import { useEffect, useState } from 'react';
import { Newspaper, RefreshCw } from 'lucide-react';
import { isStale, usePolling } from '../hooks/usePolling';
import type { NewsData } from '../types/dashboard';
import { StaleBadge } from './Card';

function ago(iso: string | null): string | null {
  if (!iso) return null;
  const minutes = Math.round((Date.now() - Date.parse(iso)) / 60_000);
  if (minutes < 1) return 'ahora';
  if (minutes < 60) return `hace ${minutes} min`;
  const hours = Math.round(minutes / 60);
  return hours < 24 ? `hace ${hours} h` : `hace ${Math.round(hours / 24)} d`;
}

export function NewsTicker({ className = '' }: { className?: string }) {
  const state = usePolling<NewsData>('/api/news', 5 * 60_000);
  const items = state.data?.items ?? [];
  const speed = state.data?.ticker_speed_seconds ?? 15;
  const [index, setIndex] = useState(0);

  useEffect(() => {
    if (items.length < 2) return;
    const timer = window.setInterval(() => setIndex((i) => i + 1), speed * 1000);
    return () => window.clearInterval(timer);
  }, [items.length, speed]);

  const item = items.length ? items[index % items.length] : null;

  return (
    <footer
      className={`flex h-20 items-center gap-6 overflow-hidden rounded-3xl border border-white/[0.06] bg-slate-900/50 px-6 shadow-2xl shadow-black/40 backdrop-blur-xl ${className}`}
    >
      <span className="flex shrink-0 items-center gap-3 text-base font-semibold uppercase tracking-[0.2em] text-slate-400">
        <Newspaper className="h-6 w-6 text-rose-300" />
        Noticias
      </span>
      {item ? (
        <div key={item.id} className="flex min-w-0 flex-1 animate-fade-in items-center gap-4">
          <span className="shrink-0 rounded-lg bg-rose-400/15 px-3 py-1 text-lg font-bold text-rose-200">{item.source}</span>
          <span className="truncate text-2xl font-semibold tracking-tight text-white">{item.title}</span>
          {ago(item.published_at) && <span className="shrink-0 text-lg text-slate-500">{ago(item.published_at)}</span>}
        </div>
      ) : (
        <span className="flex-1 text-xl text-slate-500">{state.data ? 'Sin titulares' : 'Cargando titulares…'}</span>
      )}
      {isStale(state) && <StaleBadge />}
      {items.length > 0 && (
        <span className="flex shrink-0 items-center gap-2 text-lg font-medium tabular-nums text-slate-500">
          {(index % items.length) + 1}/{items.length}
          <RefreshCw className="h-5 w-5" />
          {speed}s
        </span>
      )}
    </footer>
  );
}
