import { useEffect, useState } from 'react';
import { CompactWeatherWidget } from './CompactWeatherWidget';

const ROTATE_SECONDS = 5;

/**
 * Ubicaciones secundarias en una sola tarjeta que va rotando. Todas quedan
 * montadas (cada una mantiene su sondeo) y apiladas en la misma celda, así el
 * alto no salta al cambiar de ciudad.
 */
export function WeatherCarousel({ indexes }: { indexes: number[] }) {
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (indexes.length < 2) return;
    const timer = window.setInterval(() => setStep((s) => s + 1), ROTATE_SECONDS * 1000);
    return () => window.clearInterval(timer);
  }, [indexes.length]);

  if (indexes.length === 0) return null;
  const active = step % indexes.length;

  return (
    <div className="grid shrink-0">
      {indexes.map((index, i) => (
        <div
          key={index}
          className={`col-start-1 row-start-1 transition-opacity duration-700 ${i === active ? 'opacity-100' : 'pointer-events-none opacity-0'}`}
          aria-hidden={i !== active}
        >
          <CompactWeatherWidget index={index} />
        </div>
      ))}
    </div>
  );
}
