import { ShoppingCart, Square, SquareCheckBig } from 'lucide-react';
import { isStale, usePolling } from '../hooks/usePolling';
import type { ShoppingList } from '../types/dashboard';
import { Card, Placeholder, fadeBottom } from './Card';

/** A partir de aquí la lista se reparte en dos columnas. */
const TWO_COLUMNS_FROM = 7;

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
        list && pending > 0 ? (
          <span className="rounded-full bg-emerald-400/15 px-3 py-1 text-lg font-bold tabular-nums text-emerald-300">{pending}</span>
        ) : undefined
      }
    >
      {!list ? (
        <Placeholder>Cargando lista…</Placeholder>
      ) : list.items.length === 0 ? (
        <Placeholder>Nada pendiente</Placeholder>
      ) : (
        <ul className={`h-full overflow-hidden ${pending >= TWO_COLUMNS_FROM ? 'columns-2 gap-8' : ''}`} style={fadeBottom}>
          {list.items.map((item) => (
            <li key={item.id} className="flex break-inside-avoid items-start gap-4 py-1.5">
              {item.completed ? (
                <SquareCheckBig className="mt-1 h-7 w-7 shrink-0 text-slate-600" />
              ) : (
                <Square className="mt-1 h-7 w-7 shrink-0 text-emerald-400/80" />
              )}
              <span
                className={
                  item.completed
                    ? 'text-2xl font-medium text-slate-600 line-through decoration-2'
                    : 'text-3xl font-semibold tracking-tight text-white'
                }
              >
                {item.text}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
