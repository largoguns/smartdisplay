import {
  Cloud,
  CloudDrizzle,
  CloudFog,
  CloudLightning,
  CloudMoon,
  CloudRain,
  CloudSnow,
  CloudSun,
  Moon,
  Sun,
  type LucideIcon,
} from 'lucide-react';

interface WmoInfo {
  label: string;
  day: LucideIcon;
  night: LucideIcon;
  color: string;
}

const clear: WmoInfo = { label: 'Despejado', day: Sun, night: Moon, color: 'text-amber-300' };

// Códigos WMO usados por Open-Meteo.
const WMO: Record<number, WmoInfo> = {
  0: clear,
  1: { label: 'Mayormente despejado', day: CloudSun, night: CloudMoon, color: 'text-amber-200' },
  2: { label: 'Parcialmente nublado', day: CloudSun, night: CloudMoon, color: 'text-slate-200' },
  3: { label: 'Cubierto', day: Cloud, night: Cloud, color: 'text-slate-300' },
  45: { label: 'Niebla', day: CloudFog, night: CloudFog, color: 'text-slate-400' },
  48: { label: 'Niebla helada', day: CloudFog, night: CloudFog, color: 'text-slate-400' },
  51: { label: 'Llovizna débil', day: CloudDrizzle, night: CloudDrizzle, color: 'text-sky-300' },
  53: { label: 'Llovizna', day: CloudDrizzle, night: CloudDrizzle, color: 'text-sky-300' },
  55: { label: 'Llovizna intensa', day: CloudDrizzle, night: CloudDrizzle, color: 'text-sky-300' },
  56: { label: 'Llovizna helada', day: CloudDrizzle, night: CloudDrizzle, color: 'text-cyan-200' },
  57: { label: 'Llovizna helada', day: CloudDrizzle, night: CloudDrizzle, color: 'text-cyan-200' },
  61: { label: 'Lluvia débil', day: CloudRain, night: CloudRain, color: 'text-sky-400' },
  63: { label: 'Lluvia', day: CloudRain, night: CloudRain, color: 'text-sky-400' },
  65: { label: 'Lluvia intensa', day: CloudRain, night: CloudRain, color: 'text-blue-400' },
  66: { label: 'Lluvia helada', day: CloudRain, night: CloudRain, color: 'text-cyan-300' },
  67: { label: 'Lluvia helada', day: CloudRain, night: CloudRain, color: 'text-cyan-300' },
  71: { label: 'Nieve débil', day: CloudSnow, night: CloudSnow, color: 'text-slate-100' },
  73: { label: 'Nieve', day: CloudSnow, night: CloudSnow, color: 'text-slate-100' },
  75: { label: 'Nieve intensa', day: CloudSnow, night: CloudSnow, color: 'text-white' },
  77: { label: 'Granizo fino', day: CloudSnow, night: CloudSnow, color: 'text-slate-100' },
  80: { label: 'Chubascos', day: CloudRain, night: CloudRain, color: 'text-sky-400' },
  81: { label: 'Chubascos', day: CloudRain, night: CloudRain, color: 'text-sky-400' },
  82: { label: 'Chubascos fuertes', day: CloudRain, night: CloudRain, color: 'text-blue-400' },
  85: { label: 'Chubascos de nieve', day: CloudSnow, night: CloudSnow, color: 'text-slate-100' },
  86: { label: 'Chubascos de nieve', day: CloudSnow, night: CloudSnow, color: 'text-slate-100' },
  95: { label: 'Tormenta', day: CloudLightning, night: CloudLightning, color: 'text-violet-300' },
  96: { label: 'Tormenta con granizo', day: CloudLightning, night: CloudLightning, color: 'text-violet-300' },
  99: { label: 'Tormenta con granizo', day: CloudLightning, night: CloudLightning, color: 'text-violet-300' },
};

export function weatherInfo(code: number, isDay = true): { label: string; Icon: LucideIcon; color: string } {
  const info = WMO[code] ?? { ...clear, label: 'Desconocido' };
  return { label: info.label, Icon: isDay ? info.day : info.night, color: info.color };
}
