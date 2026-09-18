import { useCallback, useEffect, useRef, useState, type SetStateAction } from 'react';

// One bounded read at a time. A lost connection never clears the last good value.
export function usePolling<T>(read: (signal: AbortSignal) => Promise<T>, interval = 3000) {
  const [value, update] = useState<T>();
  const [error, setError] = useState(''), [receivedAt, setReceivedAt] = useState<number>();
  const [loading, setLoading] = useState(true);
  const refreshRef = useRef<() => Promise<void>>(async () => {}), revision = useRef(0);
  const setValue = useCallback((next: SetStateAction<T | undefined>) => { revision.current++; update(next); }, []);
  const refresh = useCallback(() => refreshRef.current(), []);
  useEffect(() => {
    let active = true, failures = 0, controller: AbortController | undefined, timer: ReturnType<typeof setTimeout>;
    update(undefined); setError(''); setReceivedAt(undefined); setLoading(true);
    const poll = async () => {
      if (!active || controller || document.hidden) return;
      clearTimeout(timer);
      controller = new AbortController(); const started = revision.current;
      try {
        const result = await read(controller.signal);
        if (active && started === revision.current) { update(result); setError(''); setReceivedAt(Date.now()); }
        failures = 0;
      } catch (e) { if (active) { failures++; setError((e as Error).message); } }
      finally {
        controller = undefined;
        if (active) { setLoading(false); timer = setTimeout(() => void poll(), Math.min(interval * 2 ** failures, Math.max(interval, 15000))); }
      }
    };
    const reconnect = () => { if (!document.hidden) void poll(); };
    refreshRef.current = poll; void poll();
    window.addEventListener('online', reconnect); document.addEventListener('visibilitychange', reconnect);
    return () => {
      active = false; clearTimeout(timer); controller?.abort();
      window.removeEventListener('online', reconnect); document.removeEventListener('visibilitychange', reconnect);
    };
  }, [read, interval]);
  return { value, setValue, error, receivedAt, loading, refresh };
}
