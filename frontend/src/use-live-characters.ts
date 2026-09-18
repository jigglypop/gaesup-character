import { api } from './api';
import { usePolling } from './use-polling';

export function useLiveCharacters() {
  const result = usePolling(api.list, 5000);
  return { characters: result.value?.characters || [], failure: result.error, loading: result.loading, refresh: result.refresh };
}
