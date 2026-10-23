const LOCALE = 'es-ES';

const decimal1 = new Intl.NumberFormat(LOCALE, { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const integer = new Intl.NumberFormat(LOCALE, { maximumFractionDigits: 0 });

export function formatPower(watts: number): string {
  const abs = Math.abs(watts);
  return abs >= 1000 ? `${decimal1.format(abs / 1000)} kW` : `${integer.format(abs)} W`;
}

export function formatNumber(value: number, digits = 0): string {
  return new Intl.NumberFormat(LOCALE, { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(value);
}

export function formatCompact(value: number): string {
  return new Intl.NumberFormat(LOCALE, { notation: 'compact', maximumFractionDigits: 1 }).format(value);
}

export function formatTime(date: Date): string {
  return date.toLocaleTimeString(LOCALE, { hour: '2-digit', minute: '2-digit' });
}

export function formatDuration(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`;
}

/** Antigüedad legible ("ahora", "hace 5 min", "hace 2 h", "hace 3 d"). */
export function timeAgo(iso: string | null, now = Date.now()): string | null {
  if (!iso) return null;
  const minutes = Math.round((now - Date.parse(iso)) / 60_000);
  if (minutes < 1) return 'ahora';
  if (minutes < 60) return `hace ${minutes} min`;
  const hours = Math.round(minutes / 60);
  return hours < 24 ? `hace ${hours} h` : `hace ${Math.round(hours / 24)} d`;
}

export function capitalize(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function startOfDay(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

/** "Hoy", "Mañana", "Jueves 8" o, a partir de una semana, "Jueves 15 oct". */
export function relativeDayLabel(date: Date, now: Date): string {
  const diff = Math.round((startOfDay(date).getTime() - startOfDay(now).getTime()) / 86_400_000);
  if (diff === 0) return 'Hoy';
  if (diff === 1) return 'Mañana';
  const label = date.toLocaleDateString(LOCALE, { weekday: 'long', day: 'numeric' });
  if (diff < 7) return capitalize(label);
  return capitalize(`${label} ${date.toLocaleDateString(LOCALE, { month: 'short' }).replace('.', '')}`);
}

/** Parsea fechas "YYYY-MM-DD" como fecha local (no UTC). */
export function parseLocalDate(isoDate: string): Date {
  const [y, m, d] = isoDate.split('-').map(Number);
  return new Date(y, m - 1, d);
}
