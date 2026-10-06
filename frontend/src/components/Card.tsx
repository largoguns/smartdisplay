import type { ReactNode } from 'react';
import { CloudOff, type LucideIcon } from 'lucide-react';

interface CardProps {
  title: string;
  icon: LucideIcon;
  /** Clase de color Tailwind para el icono del título. */
  accent?: string;
  stale?: boolean;
  headerRight?: ReactNode;
  className?: string;
  children: ReactNode;
}

export function Card({ title, icon: Icon, accent = 'text-slate-400', stale, headerRight, className = '', children }: CardProps) {
  return (
    <section
      className={`relative flex min-h-0 flex-col overflow-hidden rounded-3xl border border-white/[0.06] bg-slate-900/50 p-6 shadow-2xl shadow-black/40 backdrop-blur-xl ${className}`}
    >
      <header className="mb-4 flex shrink-0 items-center justify-between gap-4">
        <h2 className="flex items-center gap-3 text-base font-semibold uppercase tracking-[0.2em] text-slate-400">
          <Icon className={`h-6 w-6 ${accent}`} strokeWidth={2.25} />
          {title}
        </h2>
        <div className="flex items-center gap-3">
          {headerRight}
          {stale && <StaleBadge />}
        </div>
      </header>
      <div className="relative min-h-0 flex-1">{children}</div>
    </section>
  );
}

export function StaleBadge() {
  return (
    <span className="flex items-center gap-2 rounded-full bg-amber-500/15 px-3 py-1 text-sm font-semibold text-amber-300">
      <CloudOff className="h-4 w-4" />
      Sin actualizar
    </span>
  );
}

export function Placeholder({ children }: { children: ReactNode }) {
  return <div className="flex h-full items-center justify-center text-center text-2xl font-medium text-slate-500">{children}</div>;
}

/** Desvanece el final de listas que pueden no caber en la tarjeta. */
export const fadeBottom = {
  maskImage: 'linear-gradient(to bottom, black 85%, transparent)',
  WebkitMaskImage: 'linear-gradient(to bottom, black 85%, transparent)',
} as const;
