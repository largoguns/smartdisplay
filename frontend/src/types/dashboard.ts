// Espejo de backend/app/schemas/models.py

export type DataStatus = 'ok' | 'stale';

interface ModuleData {
  status: DataStatus;
  fetched_at: string;
}

export interface SolarData extends ModuleData {
  ppv: number;
  /** null si el inversor no tiene medidor. */
  house_consumption: number | null;
  /** W: positivo = inyección a red, negativo = consumo de red. null si no hay medidor. */
  active_power: number | null;
  /** W: positivo = descarga, negativo = carga. */
  battery_power: number | null;
  battery_soc: number | null;
  today_energy_kwh: number;
  inverter_model: string | null;
  /**
   * Origen de consumo/red: medidor del inversor; 'balance' = hogar de SEMS y red
   * estimada en vivo (FV − hogar); 'sems' = ambos de SEMS (inversor apagado).
   */
  flow_source: 'inverter' | 'balance' | 'sems' | null;
  flow_updated_at: string | null;
}

export interface SolarDayPoint {
  /** Minutos desde medianoche (hora local) del inicio del intervalo. */
  minute: number;
  pv_w: number;
  house_w: number;
}

/** Resumen del día desde SEMS: totales (kWh) y curva de generación y consumo. */
export interface SolarDay extends ModuleData {
  day: string;
  generated_kwh: number | null;
  consumed_kwh: number | null;
  /** Energía comprada a la red. */
  imported_kwh: number | null;
  /** Energía inyectada a la red. */
  exported_kwh: number | null;
  points: SolarDayPoint[];
}

export interface CalendarEvent {
  id: string;
  title: string;
  start: string;
  end: string;
  is_all_day: boolean;
  is_ongoing: boolean;
  calendar: string;
  color: string;
  location: string | null;
}

export interface CalendarData extends ModuleData {
  events: CalendarEvent[];
}

export interface CurrentWeather {
  temperature: number;
  apparent_temperature: number;
  humidity: number;
  wind_speed: number;
  weather_code: number;
  is_day: boolean;
}

export interface HourlyForecast {
  time: string;
  temperature: number;
  weather_code: number;
  precipitation_probability: number | null;
  is_day: boolean;
}

export interface DailyForecast {
  date: string;
  temperature_min: number;
  temperature_max: number;
  weather_code: number;
  precipitation_probability_max: number | null;
  sunrise: string | null;
  sunset: string | null;
}

export interface WeatherData extends ModuleData {
  location: string;
  current: CurrentWeather;
  hourly: HourlyForecast[];
  daily: DailyForecast[];
}

export interface WeatherLocationInfo {
  index: number;
  name: string;
}

export interface ShoppingItem {
  id: string;
  text: string;
  completed: boolean;
}

export interface ShoppingList extends ModuleData {
  title: string;
  updated_at: string | null;
  items: ShoppingItem[];
}

export interface NasVolume {
  mount_point: string;
  label: string;
  total_gb: number;
  used_gb: number;
  percent: number;
}

export interface NasStatus extends Omit<ModuleData, 'status'> {
  status: 'healthy' | 'degraded' | 'stale';
  hostname: string | null;
  uptime_seconds: number | null;
  cpu: { usage_percent: number };
  memory: { total_gb: number; used_gb: number; percent: number };
  storage: NasVolume[];
}

export interface AdguardStats extends ModuleData {
  protection_enabled: boolean;
  queries_24h: number;
  blocked_24h: number;
  block_ratio_percent: number;
}

export interface Track {
  title: string;
  artist: string;
  album: string;
  album_art_url: string | null;
  duration_ms: number;
  progress_ms: number;
  device_name: string | null;
}

export interface NowPlaying extends ModuleData {
  is_active: boolean;
  account: string | null;
  track: Track | null;
}

export interface NewsItem {
  id: string;
  title: string;
  source: string;
  link: string | null;
  published_at: string | null;
}

export interface NewsData extends ModuleData {
  ticker_speed_seconds: number;
  items: NewsItem[];
}

export interface AnimeEpisode {
  id: number;
  title: string;
  thumbnail_url: string | null;
  /** Capítulos nuevos desde la última vez que se marcaron como vistos. */
  new_count: number;
}

/** Solo las series con capítulos nuevos. */
export interface AnimeData extends ModuleData {
  items: AnimeEpisode[];
}
