import { useLayoutEffect, useRef, useState } from 'react';
import { ShoppingCart, Square, SquareCheckBig } from 'lucide-react';
import { useElementHeight } from '../hooks/useElementHeight';
import { isStale, usePolling } from '../hooks/usePolling';
import type { ShoppingItem, ShoppingList } from '../types/dashboard';
import { Card, Placeholder, UpdatedAgo } from './Card';

/** A partir de aquí la lista se reparte en dos columnas. */
const TWO_COLUMNS_FROM = 7;

/** Tamaños de texto de mayor a menor; el último es el mínimo legible a distancia. */
const SIZES = [
  { pending: 'text-3xl', completed: 'text-2xl', icon: 'h-7 w-7', row: 'py-1.5' },
  { pending: 'text-2xl', completed: 'text-xl', icon: 'h-6 w-6', row: 'py-1' },
  { pending: 'text-xl', completed: 'text-lg', icon: 'h-5 w-5', row: 'py-1' },
] as const;

function overflows(el: HTMLElement): boolean {
  // Con columnas, lo que no cabe crea columnas extra a la derecha.
  return el.scrollHeight > el.clientHeight + 1 || el.scrollWidth > el.clientWidth + 1;
}

/**
 * Reduce el texto hasta que la lista quepa; si ni con el tamaño mínimo cabe,
 * muestra solo los primeros elementos y "y N más".
 */
function FittedList({ items, columns }: { items: ShoppingItem[]; columns: 1 | 2 }) {
  const [wrapperRef, height] = useElementHeight<HTMLDivElement>();
  const listRef = useRef<HTMLUListElement>(null);
  const key = `${height}|${columns}|${items.map((i) => `${i.id}:${i.completed}:${i.text}`).join('\n')}`;
  const [fit, setFit] = useState({ key: '', level: 0, shown: items.length });
  // Datos o tamaño nuevos: se vuelve a probar desde el tamaño más grande.
  const current = fit.key === key ? fit : { key, level: 0, shown: items.length };

  // Sin dependencias: se ajusta paso a paso antes de pintar hasta que no desborda.
  useLayoutEffect(() => {
    const list = listRef.current;
    if (!list) return;
    if (!overflows(list)) {
      if (fit !== current) setFit(current);
    } else if (current.level < SIZES.length - 1) {
      setFit({ ...current, level: current.level + 1 });
    } else if (current.shown > 1) {
      setFit({ ...current, shown: current.shown - 1 });
    }
  });

  const size = SIZES[current.level];
  const hidden = items.length - current.shown;

  return (
    <div ref={wrapperRef} className="flex h-full flex-col">
      <ul ref={listRef} className={`min-h-0 flex-1 overflow-hidden ${columns === 2 ? 'columns-2 gap-8' : ''}`}>
        {items.slice(0, current.shown).map((item) => (
          <li key={item.id} className={`flex break-inside-avoid items-start gap-4 ${size.row}`}>
            {item.completed ? (
              <SquareCheckBig className={`mt-1 shrink-0 text-slate-600 ${size.icon}`} />
            ) : (
              <Square className={`mt-1 shrink-0 text-emerald-400/80 ${size.icon}`} />
            )}
            <span
              className={
                item.completed
                  ? `${size.completed} font-medium text-slate-600 line-through decoration-2`
                  : `${size.pending} font-semibold tracking-tight text-white`
              }
            >
              {item.text}
            </span>
          </li>
        ))}
      </ul>
      {hidden > 0 && (
        <p className="shrink-0 pt-2 text-xl font-semibold text-slate-400">
          y {hidden} {hidden === 1 ? 'elemento' : 'elementos'} más
        </p>
      )}
    </div>
  );
}

export function KeepShoppingWidget({ className = '' }: { className?: string }) {
  const state = usePolling<ShoppingList>('/api/keep/shopping-list', 30_000);
  const list = state.data;
  const pending = list?.items.filter((item) => !item.completed).length ?? 0;

  return (
    <Card
      title={list?.title ?? 'La compra'}
      icon={ShoppingCart}
      accent="text-emerald-400"
      stale={isStale(state)}
      className={className}
      headerRight={
        list && (
          <>
            <UpdatedAgo at={list.fetched_at} />
            {pending > 0 && (
              <span className="rounded-full bg-emerald-400/15 px-3 py-1 text-lg font-bold tabular-nums text-emerald-300">{pending}</span>
            )}
          </>
        )
      }
    >
      {!list ? (
        <Placeholder>Cargando lista…</Placeholder>
      ) : list.items.length === 0 ? (
        <Placeholder>Nada pendiente</Placeholder>
      ) : (
        <FittedList items={list.items} columns={pending >= TWO_COLUMNS_FROM ? 2 : 1} />
      )}
    </Card>
  );
}
