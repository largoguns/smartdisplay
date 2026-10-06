import { CalendarDays } from 'lucide-react';
import { useNow } from '../hooks/useNow';
import { isStale, usePolling } from '../hooks/usePolling';
import { formatTime, relativeDayLabel, startOfDay } from '../lib/format';
import type { CalendarData, CalendarEvent } from '../types/dashboard';
import { Card, Placeholder, fadeBottom } from './Card';

interface DayGroup {
  key: number;
  label: string;
  events: CalendarEvent[];
}

function groupByDay(events: CalendarEvent[], now: Date): DayGroup[] {
  const today = startOfDay(now).getTime();
  const groups = new Map<number, DayGroup>();
  for (const event of events) {
    if (new Date(event.end) <= now) continue; // ya terminado
    // Los eventos que empezaron antes de hoy (multi-día) se agrupan en "Hoy".
    const key = Math.max(startOfDay(new Date(event.start)).getTime(), today);
    if (!groups.has(key)) groups.set(key, { key, label: relativeDayLabel(new Date(key), now), events: [] });
    groups.get(key)!.events.push(event);
  }
  return [...groups.values()].sort((a, b) => a.key - b.key);
}

function EventRow({ event, now }: { event: CalendarEvent; now: Date }) {
  const start = new Date(event.start);
  const ongoing = start <= now && now < new Date(event.end);
  return (
    <li className={`flex items-stretch gap-4 rounded-2xl px-3 py-2.5 ${ongoing ? 'bg-white/[0.06] ring-1 ring-white/10' : ''}`}>
      <span className="w-1.5 shrink-0 rounded-full" style={{ backgroundColor: event.color }} />
      <span className="w-28 shrink-0 whitespace-nowrap pt-0.5 text-2xl font-bold tabular-nums tracking-tight text-slate-200">
        {event.is_all_day ? <span className="text-sm font-semibold uppercase tracking-wide text-slate-400">Todo el día</span> : formatTime(start)}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-2xl font-semibold tracking-tight text-white">{event.title}</span>
        {event.location && <span className="block truncate text-base text-slate-400">{event.location}</span>}
      </span>
      {ongoing && !event.is_all_day && (
        <span className="self-center rounded-full bg-emerald-400/15 px-3 py-1 text-sm font-bold uppercase tracking-wider text-emerald-300 animate-pulse">
          Ahora
        </span>
      )}
    </li>
  );
}

export function CalendarWidget({ className = '' }: { className?: string }) {
  const state = usePolling<CalendarData>('/api/calendar', 60_000);
  const now = useNow(30_000);
  const groups = state.data ? groupByDay(state.data.events, now) : [];

  return (
    <Card title="Agenda" icon={CalendarDays} accent="text-sky-400" stale={isStale(state)} className={className}>
      {!state.data ? (
        <Placeholder>Cargando calendario…</Placeholder>
      ) : groups.length === 0 ? (
        <Placeholder>Sin eventos esta semana</Placeholder>
      ) : (
        <div className="h-full space-y-4 overflow-hidden" style={fadeBottom}>
          {groups.map((group) => (
            <section key={group.key}>
              <h3 className={`mb-1 text-lg font-bold uppercase tracking-[0.15em] ${group.label === 'Hoy' ? 'text-sky-300' : 'text-slate-500'}`}>
                {group.label}
              </h3>
              <ul className="space-y-1">
                {group.events.map((event) => (
                  <EventRow key={event.id} event={event} now={now} />
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}
    </Card>
  );
}
