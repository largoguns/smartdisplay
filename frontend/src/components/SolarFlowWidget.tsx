import {
  BatteryCharging,
  BatteryFull,
  BatteryLow,
  BatteryMedium,
  House,
  Sun,
  UtilityPole,
  Zap,
  type LucideIcon,
} from 'lucide-react';
import { useSolarSocket } from '../hooks/useSolarSocket';
import { formatNumber, formatPower, formatTime } from '../lib/format';
import { Card, Placeholder } from './Card';

/** Valor mostrado cuando el inversor no puede medir algo. */
const UNKNOWN = '—';

/** Por debajo de este valor no se anima el flujo (ruido de medida). */
const FLOW_THRESHOLD_W = 20;

const COLORS = {
  solar: '#fbbf24',
  home: '#38bdf8',
  export: '#34d399',
  import: '#fb7185',
  battery: '#a78bfa',
  idle: '#475569',
  inverter: '#94a3b8',
};

interface Point {
  x: number;
  y: number;
  r: number;
}

// Layout horizontal compacto (tarjeta de media altura), viewBox 600x280:
// paneles a la izquierda con la energía del día debajo; hogar y red a la derecha.
const VIEWBOX = '0 0 600 280';
const NODES = {
  solar: { x: 95, y: 130, r: 52 },
  inverter: { x: 255, y: 130, r: 32 },
  home: { x: 410, y: 68, r: 48 },
  grid: { x: 410, y: 206, r: 48 },
  battery: { x: 255, y: 240, r: 32 },
} satisfies Record<string, Point>;

function flowDuration(watts: number): string {
  // Más potencia → flujo más rápido, dentro de un rango sutil.
  return `${Math.max(0.45, 2.2 - Math.log10(Math.max(Math.abs(watts), 10)) * 0.45).toFixed(2)}s`;
}

/** Línea entre dos nodos; anima en el sentido from→to (o al revés si `reverse`). */
function FlowLine({ from, to, watts, color, reverse = false, animate }: { from: Point; to: Point; watts: number; color: string; reverse?: boolean; animate: boolean }) {
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const len = Math.hypot(dx, dy);
  const ux = dx / len;
  const uy = dy / len;
  const x1 = from.x + ux * (from.r + 6);
  const y1 = from.y + uy * (from.r + 6);
  const x2 = to.x - ux * (to.r + 6);
  const y2 = to.y - uy * (to.r + 6);
  const active = animate && Math.abs(watts) >= FLOW_THRESHOLD_W;

  return (
    <g>
      <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="#1e293b" strokeWidth={6} strokeLinecap="round" />
      {active && (
        <line
          x1={x1}
          y1={y1}
          x2={x2}
          y2={y2}
          stroke={color}
          strokeWidth={6}
          strokeLinecap="round"
          className={`power-flow ${reverse ? 'power-flow-reverse' : ''}`}
          style={{ animationDuration: flowDuration(watts), filter: `drop-shadow(0 0 6px ${color})` }}
        />
      )}
    </g>
  );
}

interface NodeProps {
  at: Point;
  icon: LucideIcon;
  color: string;
  active: boolean;
  value?: string;
  caption?: string;
  captionPosition?: 'above' | 'below' | 'right';
}

function FlowNode({ at, icon: Icon, color, active, value, caption, captionPosition = 'below' }: NodeProps) {
  const iconSize = value ? 30 : 32;
  const caption_ = {
    above: { x: at.x, y: at.y - at.r - 14, anchor: 'middle' as const },
    below: { x: at.x, y: at.y + at.r + 26, anchor: 'middle' as const },
    right: { x: at.x + at.r + 14, y: at.y + 6, anchor: 'start' as const },
  }[captionPosition];
  return (
    <g>
      <circle cx={at.x} cy={at.y} r={at.r} fill="#0f172a" stroke={color} strokeWidth={3} strokeOpacity={active ? 0.95 : 0.3} />
      {active && <circle cx={at.x} cy={at.y} r={at.r} fill={color} fillOpacity={0.08} />}
      <Icon
        x={at.x - iconSize / 2}
        y={value ? at.y - 38 : at.y - iconSize / 2}
        size={iconSize}
        color={active ? color : COLORS.idle}
        strokeWidth={2}
      />
      {value && (
        <text x={at.x} y={at.y + 24} textAnchor="middle" fontSize={22} fontWeight={700} fill="#f8fafc">
          {value}
        </text>
      )}
      {caption && (
        <text x={caption_.x} y={caption_.y} textAnchor={caption_.anchor} fontSize={16} fontWeight={600} letterSpacing={1.2} fill={active ? color : '#64748b'}>
          {caption.toUpperCase()}
        </text>
      )}
    </g>
  );
}

function batteryIcon(soc: number | null, charging: boolean): LucideIcon {
  if (charging) return BatteryCharging;
  if (soc === null || soc >= 70) return BatteryFull;
  return soc >= 30 ? BatteryMedium : BatteryLow;
}

export function SolarFlowWidget({ className = '' }: { className?: string }) {
  const { data } = useSolarSocket();
  const stale = data?.status === 'stale';

  if (!data) {
    return (
      <Card title="Energía solar" icon={Sun} accent="text-amber-400" className={className}>
        <Placeholder>Conectando con el inversor…</Placeholder>
      </Card>
    );
  }

  // Con datos antiguos no se anima nada: el flujo mostrado no sería real.
  const animate = !stale;
  // Sin medidor (p. ej. inversores DT) no se conoce ni la red ni el consumo.
  const grid = data.active_power;
  const house = data.house_consumption;
  const exporting = grid !== null && grid >= FLOW_THRESHOLD_W;
  const importing = grid !== null && grid <= -FLOW_THRESHOLD_W;
  const gridColor = exporting ? COLORS.export : importing ? COLORS.import : COLORS.idle;
  const hasBattery = data.battery_power !== null || data.battery_soc !== null;
  const batteryPower = data.battery_power ?? 0;
  const charging = batteryPower <= -FLOW_THRESHOLD_W;
  const producing = data.ppv >= FLOW_THRESHOLD_W;

  return (
    <Card
      title="Energía solar"
      icon={Sun}
      accent="text-amber-400"
      stale={stale}
      headerRight={
        (data.flow_source === 'balance' || data.flow_source === 'sems') && (
          <span className="text-sm font-medium text-slate-500">
            {data.flow_source === 'balance' ? 'Red estimada · consumo vía SEMS' : 'Hogar y red vía SEMS'}
            {data.flow_updated_at && ` ${formatTime(new Date(data.flow_updated_at))}`}
          </span>
        )
      }
      className={className}
    >
      <div className={`h-full transition-opacity duration-700 ${stale ? 'opacity-50' : ''}`}>
        <svg viewBox={VIEWBOX} className="h-full w-full" preserveAspectRatio="xMidYMid meet">
          <FlowLine from={NODES.solar} to={NODES.inverter} watts={data.ppv} color={COLORS.solar} animate={animate} />
          <FlowLine from={NODES.inverter} to={NODES.home} watts={house ?? 0} color={COLORS.home} animate={animate} />
          <FlowLine from={NODES.inverter} to={NODES.grid} watts={grid ?? 0} color={gridColor} reverse={importing} animate={animate} />
          {hasBattery && (
            <FlowLine from={NODES.inverter} to={NODES.battery} watts={batteryPower} color={COLORS.battery} reverse={!charging} animate={animate} />
          )}

          <FlowNode at={NODES.solar} icon={Sun} color={COLORS.solar} active={producing} value={formatPower(data.ppv)} caption="Paneles" captionPosition="above" />
          <FlowNode at={NODES.inverter} icon={Zap} color={COLORS.inverter} active={!stale} />
          <FlowNode
            at={NODES.home}
            icon={House}
            color={house !== null ? COLORS.home : COLORS.idle}
            active={house !== null}
            value={house !== null ? formatPower(house) : UNKNOWN}
            caption="Hogar"
            captionPosition="right"
          />
          <FlowNode
            at={NODES.grid}
            icon={UtilityPole}
            color={gridColor}
            active={exporting || importing}
            value={grid !== null ? formatPower(grid) : UNKNOWN}
            caption={grid === null ? 'Sin medidor' : exporting ? 'Exportando' : importing ? 'Importando' : 'Red'}
            captionPosition="right"
          />
          {hasBattery && (
            <FlowNode
              at={NODES.battery}
              icon={batteryIcon(data.battery_soc, charging)}
              color={COLORS.battery}
              active={Math.abs(batteryPower) >= FLOW_THRESHOLD_W}
              value={data.battery_soc !== null ? `${formatNumber(data.battery_soc)} %` : formatPower(batteryPower)}
              captionPosition="right"
            />
          )}

          {/* Energía generada hoy, bajo los paneles. */}
          <text x={NODES.solar.x} y={NODES.solar.y + NODES.solar.r + 44} textAnchor="middle" fontSize={34} fontWeight={700} fill="#fcd34d">
            {formatNumber(data.today_energy_kwh, 1)}
            <tspan fontSize={18} fontWeight={600} fill="#fde68a" fillOpacity={0.7}> kWh</tspan>
          </text>
          <text x={NODES.solar.x} y={NODES.solar.y + NODES.solar.r + 68} textAnchor="middle" fontSize={13} fontWeight={600} letterSpacing={1.5} fill="#fde68a" fillOpacity={0.6}>
            GENERADO HOY
          </text>
        </svg>
      </div>
    </Card>
  );
}
