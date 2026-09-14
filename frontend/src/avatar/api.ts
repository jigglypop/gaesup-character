import { SaveSystem, type AssetRecord, type SaveAdapter, type SaveBlob } from 'gaesup-world';
import { ApiError, request } from '../api';
import { avatarManifestFromRecord, parseAvatarState } from './core/manifest';
import type { AvatarState } from './core/types';
import type { AvatarRuntime } from './runtime/AvatarRuntime';

export type SavedAvatar = { revision: string; state: AvatarState };
export const avatarApi = {
  catalog: async () => {
    const result = await request<{ assets: AssetRecord[] }>('/api/avatars/catalog');
    for (const asset of result.assets) avatarManifestFromRecord(asset);
    return result.assets;
  },
  read: () => request<SavedAvatar>('/api/avatars/me'),
};
type PendingSave = { key: string; revision: string; state: AvatarState };
const pendingKey = 'atelier.avatar.pending.v1';

/** Public gaesup-world SaveSystem domain; backend owns persistence and revision checks. */
export function createAvatarPersistence(avatar: AvatarRuntime, initialRevision: string) {
  let revision = initialRevision;
  let hydration = Promise.resolve();
  const adapter: SaveAdapter = {
    async read() {
      const result = await avatarApi.read();
      revision = result.revision;
      return { version: 1, savedAt: 0, domains: { avatar: parseAvatarState(result.state) } };
    },
    async write(_slot, blob: SaveBlob) {
      const pendingText = sessionStorage.getItem(pendingKey);
      const pending: PendingSave = pendingText ? JSON.parse(pendingText) : {
        key: crypto.randomUUID(), revision, state: parseAvatarState(blob.domains.avatar),
      };
      parseAvatarState(pending.state);
      sessionStorage.setItem(pendingKey, JSON.stringify(pending));
      try {
        const result = await request<SavedAvatar>('/api/avatars/me', {
          method: 'PUT', headers: { 'Content-Type': 'application/json', 'If-Match': pending.revision, 'Idempotency-Key': pending.key },
          body: JSON.stringify(pending.state),
        });
        revision = result.revision;
        sessionStorage.removeItem(pendingKey);
        // A recovered response may acknowledge an older outfit. Keep visible state truthful.
        if (pendingText) await avatar.restore(result.state);
      } catch (error) {
        if (error instanceof ApiError && error.status >= 400 && error.status < 500) sessionStorage.removeItem(pendingKey);
        throw error;
      }
    },
    async list() { return ['avatar']; },
    async remove() { throw new Error('장착 저장 삭제는 지원하지 않습니다.'); },
  };
  const system = new SaveSystem({ adapter, defaultSlot: 'avatar', currentVersion: 1 });
  system.register({ key: 'avatar', serialize: avatar.getState, hydrate: value => {
    const state = parseAvatarState(value);
    hydration = avatar.restore(state);
  } });
  return {
    system,
    hasPending: () => !!sessionStorage.getItem(pendingKey),
    save: () => system.save(),
    async load() { await system.load(); await hydration; sessionStorage.removeItem(pendingKey); },
  };
}
