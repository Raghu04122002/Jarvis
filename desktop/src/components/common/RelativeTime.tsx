import { useSyncExternalStore } from "react";
import { formatDate, formatRelativeTime } from "@/lib/formatters";

// One shared 30s ticker for every RelativeTime on screen.
let tick = Date.now();
const listeners = new Set<() => void>();
let timer: ReturnType<typeof setInterval> | null = null;

function subscribe(cb: () => void) {
  listeners.add(cb);
  if (!timer) {
    timer = setInterval(() => {
      tick = Date.now();
      listeners.forEach((l) => l());
    }, 30_000);
  }
  return () => {
    listeners.delete(cb);
    if (listeners.size === 0 && timer) {
      clearInterval(timer);
      timer = null;
    }
  };
}

/** "2m ago" that refreshes itself; full date/time on hover. */
export function RelativeTime({ iso, className }: { iso: string; className?: string }) {
  const now = useSyncExternalStore(subscribe, () => tick);
  return (
    <time dateTime={iso} title={formatDate(iso)} className={className}>
      {formatRelativeTime(iso, now)}
    </time>
  );
}
