import type { ReactNode } from 'react';
import { HardDrive, ShieldCheck, ShieldOff } from 'lucide-react';
import { isStale, usePolling } from '../hooks/usePolling';
import { formatCompact, formatNumber } from '../lib/format';
import type { AdguardStats, NasStatus } from '../types/dashboard';

type Tone = 'good' | 'warn' | 'bad' | 'muted';

const TONES: Record<Tone, string> = {
  good: 'border-emerald-400/25 bg-emerald-400/10 text-emerald-300',
  warn: 'border-amber-400/30 bg-amber-400/10 text-amber-300',
  bad: 'border-rose-400/30 bg-rose-400/10 text-rose-300',
  muted: 'border-white/10 bg-slate-800/50 text-slate-500',
};

function Pill({ tone, icon, children }: { tone: Tone; icon: ReactNode; children: ReactNode }) {
  return (
    <div className={`flex items-center gap-3 rounded-full border px-5 py-2.5 text-xl font-semibold backdrop-blur-md ${TONES[tone]}`}>
      {icon}
      {children}
    </div>
  );
}

function usageTone(percent: number): Tone {
  if (percent >= 90) return 'bad';
  if (percent >= 75) return 'warn';
  return 'good';
}

export function SystemPills() {
  const adguard = usePolling<AdguardStats>('/api/network/adguard', 60_000);
  const nas = usePolling<NasStatus>('/api/system/nas', 30_000);

  const ag = adguard.data;
  const agTone: Tone = !ag || isStale(adguard) ? 'muted' : ag.protection_enabled ? 'good' : 'bad';

  const n = nas.data;
  const nasStale = nas.error !== null || n?.status === 'stale';
  const maxDisk = n?.storage.reduce((max, v) => Math.max(max, v.percent), 0) ?? 0;
  const nasTone: Tone = !n || nasStale ? 'muted' : n.status === 'degraded' ? 'warn' : 'good';

  return (
    <div className="flex items-center gap-4">
      {ag && (
        <Pill tone={agTone} icon={ag.protection_enabled ? <ShieldCheck className="h-6 w-6" /> : <ShieldOff className="h-6 w-6" />}>
          <span>AdGuard</span>
          <span className="tabular-nums text-white">{formatNumber(ag.block_ratio_percent, 1)} %</span>
          <span className="text-base font-medium opacity-70">{formatCompact(ag.blocked_24h)} bloqueadas</span>
        </Pill>
      )}
      {n && (
        <Pill tone={nasTone} icon={<HardDrive className="h-6 w-6" />}>
          <span>NAS</span>
          <Metric label="CPU" value={n.cpu.usage_percent} />
          <Metric label="RAM" value={n.memory.percent} />
          {n.storage.length > 0 && <Metric label="Disco" value={maxDisk} />}
        </Pill>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  const color = { good: 'text-white', warn: 'text-amber-300', bad: 'text-rose-300', muted: 'text-white' }[usageTone(value)];
  return (
    <span className="flex items-baseline gap-1.5">
      <span className="text-base font-medium opacity-70">{label}</span>
      <span className={`tabular-nums ${color}`}>{formatNumber(value)} %</span>
    </span>
  );
}
