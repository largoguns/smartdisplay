import { ArrowDownToLine, ArrowUpFromLine, type LucideIcon } from 'lucide-react';
import { useNow } from '../hooks/useNow';
import { isStale, usePolling } from '../hooks/usePolling';
import { formatNumber } from '../lib/format';
import type { SolarDay, SolarDayPoint } from '../types/dashboard';

const MINUTES_PER_DAY = 24 * 60;
const HOUR_MARKS = [6, 12, 18];

// Coordenadas internas de la gráfica: se estira al tamaño disponible
// (preserveAspectRatio="none"), por eso los textos van en HTML encima.
const W = 1000;
const H = 100;

const COLORS = {
  pv: '#fbbf24',
  house: '#38bdf8',
  import: '#fb7185',
  export: '#34d399',
};

function x(minute: number): number {
  return (minute / MINUTES_PER_DAY) * W;
}

function linePath(points: SolarDayPoint[], value: (p: SolarDayPoint) => number, scaleW: number): string {
  return points.map((p, i) => `${i ? 'L' : 'M'}${x(p.minute).toFixed(1)},${(H - (value(p) / scaleW) * H).toFixed(1)}`).join('');
}

function Kpi({ icon: Icon, label, kwh, color }: { icon: LucideIcon; label: string; kwh: number | null; color: string }) {
  return (
    <div className="flex min-w-0 flex-1 items-center gap-3 rounded-2xl bg-white/[0.04] px-4 py-1.5">
      <Icon className="h-6 w-6 shrink-0" style={{ color }} strokeWidth={2.25} />
      <div className="min-w-0">
        <div className="truncate text-xs font-semibold uppercase tracking-wider text-slate-400">{label}</div>
        <div className="text-2xl font-bold leading-tight" style={{ color }}>
          {kwh !== null ? formatNumber(kwh, 1) : '—'}
          <span className="ml-1 text-base font-semibold opacity-70">kWh</span>
        </div>
      </div>
    </div>
  );
}

function DayChart({ points, nowMinute }: { points: SolarDayPoint[]; nowMinute: number | null }) {
  const peak = Math.max(1000, ...points.map((p) => Math.max(p.pv_w, p.house_w)));
  const scaleKw = Math.ceil(peak / 1000);
  const scaleW = scaleKw * 1000;
  const pv = linePath(points, (p) => p.pv_w, scaleW);
  const last = points[points.length - 1];

  return (
    <div className="relative h-full w-full">
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="absolute inset-0 h-full w-full overflow-visible">
        <defs>
          <linearGradient id="solar-day-pv" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={COLORS.pv} stopOpacity={0.45} />
            <stop offset="100%" stopColor={COLORS.pv} stopOpacity={0.05} />
          </linearGradient>
        </defs>
        {Array.from({ length: scaleKw - 1 }, (_, i) => (
          <line key={i} x1={0} x2={W} y1={H - ((i + 1) / scaleKw) * H} y2={H - ((i + 1) / scaleKw) * H} stroke="#334155" strokeWidth={1} strokeDasharray="4 6" vectorEffect="non-scaling-stroke" />
        ))}
        {HOUR_MARKS.map((h) => (
          <line key={h} x1={x(h * 60)} x2={x(h * 60)} y1={0} y2={H} stroke="#334155" strokeWidth={1} strokeDasharray="4 6" vectorEffect="non-scaling-stroke" />
        ))}
        <line x1={0} x2={W} y1={H} y2={H} stroke="#475569" strokeWidth={1.5} vectorEffect="non-scaling-stroke" />
        {points.length > 1 && last && (
          <>
            <path d={`${pv}L${x(last.minute).toFixed(1)},${H}L${x(points[0].minute).toFixed(1)},${H}Z`} fill="url(#solar-day-pv)" />
            <path d={pv} fill="none" stroke={COLORS.pv} strokeWidth={2.5} strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
            <path d={linePath(points, (p) => p.house_w, scaleW)} fill="none" stroke={COLORS.house} strokeWidth={2.5} strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
          </>
        )}
        {nowMinute !== null && (
          <line x1={x(nowMinute)} x2={x(nowMinute)} y1={0} y2={H} stroke="#94a3b8" strokeWidth={1.5} strokeOpacity={0.6} vectorEffect="non-scaling-stroke" />
        )}
      </svg>

      <span className="absolute left-1 top-0 text-sm font-semibold text-slate-500">{scaleKw} kW</span>
      <div className="absolute right-1 top-0 flex gap-4 text-sm font-semibold">
        <span style={{ color: COLORS.pv }}>● Generación</span>
        <span style={{ color: COLORS.house }}>● Consumo</span>
      </div>
      {HOUR_MARKS.map((h) => (
        <span key={h} className="absolute top-full mt-1 -translate-x-1/2 text-sm font-medium text-slate-500" style={{ left: `${(h / 24) * 100}%` }}>
          {h}h
        </span>
      ))}
    </div>
  );
}

/** Energía intercambiada con la red hoy y curva de generación y consumo (SEMS). */
export function SolarDayPanel() {
  const state = usePolling<SolarDay>('/api/solar/today', 5 * 60_000);
  const now = useNow(60_000);
  const day = state.data;
  if (!day) return null;

  const today = now.toLocaleDateString('sv-SE') === day.day;
  const nowMinute = today ? now.getHours() * 60 + now.getMinutes() : null;

  return (
    <div className={`flex h-full min-h-0 flex-col gap-3 transition-opacity duration-700 ${isStale(state) ? 'opacity-50' : ''}`}>
      <div className="flex shrink-0 gap-3">
        <Kpi icon={ArrowDownToLine} label="Comprado a la red" kwh={day.imported_kwh} color={COLORS.import} />
        <Kpi icon={ArrowUpFromLine} label="Inyectado a la red" kwh={day.exported_kwh} color={COLORS.export} />
      </div>
      <div className="min-h-[80px] flex-1 pb-6 pt-6">
        <DayChart points={day.points} nowMinute={nowMinute} />
      </div>
    </div>
  );
}
