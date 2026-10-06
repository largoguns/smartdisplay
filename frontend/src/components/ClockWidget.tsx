import { useNow } from '../hooks/useNow';
import { capitalize } from '../lib/format';

export function ClockWidget() {
  const now = useNow();
  const time = now.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' });
  const date = capitalize(now.toLocaleDateString('es-ES', { weekday: 'long', day: 'numeric', month: 'long' }));
  const [weekday, rest] = date.split(', ');

  return (
    <div className="flex items-baseline gap-6">
      <span className="text-7xl font-bold tabular-nums tracking-tight text-white">{time}</span>
      <span className="text-3xl font-semibold tracking-tight text-slate-300">
        {weekday}
        {rest && <span className="text-slate-400">, {rest}</span>}
      </span>
    </div>
  );
}
