import { useEffect, useState } from 'react';

/** Fecha actual re-renderizada cada `intervalMs`, alineada al segundo. */
export function useNow(intervalMs = 1_000): Date {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    let interval: number | undefined;
    const align = window.setTimeout(() => {
      setNow(new Date());
      interval = window.setInterval(() => setNow(new Date()), intervalMs);
    }, 1_000 - (Date.now() % 1_000));
    return () => {
      window.clearTimeout(align);
      window.clearInterval(interval);
    };
  }, [intervalMs]);
  return now;
}
