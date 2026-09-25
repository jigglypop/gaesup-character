import { isDefinitiveRejection, request } from '../api';
import type { FactoryJob, FitProfile } from '../factory/api';
import type { ExpressionName, FaceLayout } from '../texture-expressions';
import type { MeshyOptions } from './meshy-options';

export type PartMetadata = { name?: string; deleted?: boolean };
export type Catalog = { revision: string; items: Record<string, { name?: string; archived?: boolean; deleted?: boolean }>; parts: Record<string, PartMetadata>; characters?: Record<string, { deleted?: boolean }> };
export function isCatalogJobDeleted(job: FactoryJob, catalog?: Catalog) {
  return !!(catalog?.items[job.id]?.deleted || catalog?.characters?.[job.character_id || job.id]?.deleted);
}
export type VariantInput = { base_job_id: string; base_version: string; slots: string[]; hair_length: 'source' | 'short' | 'long'; bottom_kind?: 'source' | 'pants' | 'skirt'; descriptions: Record<string, string>; meshy_options?: MeshyOptions };
export type SinglePartInput = { base_job_id: string; base_version: string; slot: string; hair_length: 'source' | 'short' | 'long'; bottom_kind: 'source' | 'pants' | 'skirt'; view_mode?: 'front_side' | 'front_side_back'; fit_profile?: FitProfile; meshy_options?: MeshyOptions; part_method?: 'isolated' | 'body_shell' | 'worn'; model_provider?: 'meshy' | 'tripo' };
export type Tile = { id: string; surface: string; size: number; seed: number; gpu: { estimated_bytes_with_mips: number }; artifacts: { name: string; url: string }[] };
export type Animal = {id:string;name:string;species:'dog'|'cat'|'dragon';status:string;error?:string;bones?:number;artifacts:{name:string;url:string}[]};
export type HeadPartAsset = { name: string; sha256: string; url: string };
export type Expression = { id: string; name: ExpressionName; layout: FaceLayout; materials: {material:number;file:string;base_file?:string}[]; artifacts:{name:string;url:string;sha256:string}[]; head?: HeadPartAsset };
export type ExpressionLibrary = { items: Expression[]; selected: string | null; revision: string };
const pendingKey = 'gaesup.studio.variant.v1';
const singlePartPendingKey = 'gaesup.studio.single-part.v1';
const singlePartSlots = ['hair', 'hat', 'top', 'bottom', 'shoes', 'weapon', 'tool', 'glasses'];
type PendingVariant = { key: string; input: VariantInput };
export type PendingSinglePart = { key: string; input: SinglePartInput };
function variantRecovery(): { pending: PendingVariant | null; error: string } {
  try {
    const raw = localStorage.getItem(pendingKey);
    if (!raw) return { pending: null, error: '' };
    const pending = JSON.parse(raw) as PendingVariant;
    if (!pending || typeof pending.key !== 'string' || !pending.key || !pending.input
      || typeof pending.input.base_job_id !== 'string' || typeof pending.input.base_version !== 'string'
      || !Array.isArray(pending.input.slots) || !pending.input.slots.every(slot => typeof slot === 'string')
      || !['source', 'short', 'long'].includes(pending.input.hair_length)
      || (pending.input.bottom_kind != null && !['source', 'pants', 'skirt'].includes(pending.input.bottom_kind))
      || !pending.input.descriptions || typeof pending.input.descriptions !== 'object') throw new Error();
    return { pending, error: '' };
  } catch {
    return { pending: null, error: '저장된 파츠 요청을 읽을 수 없습니다. 기존 요청 기록을 확인해야 새 생성을 접수할 수 있습니다.' };
  }
}
function clearVariant(key: string) {
  if (variantRecovery().pending?.key === key) localStorage.removeItem(pendingKey);
}
function singlePartRecovery(): { pending: PendingSinglePart | null; error: string } {
  try {
    const raw = localStorage.getItem(singlePartPendingKey);
    if (!raw) return { pending: null, error: '' };
    const pending = JSON.parse(raw) as PendingSinglePart;
    if (!pending || typeof pending.key !== 'string' || !pending.key || !pending.input
      || typeof pending.input.base_job_id !== 'string' || typeof pending.input.base_version !== 'string'
      || !singlePartSlots.includes(pending.input.slot)
      || !['source', 'short', 'long'].includes(pending.input.hair_length)
      || !['source', 'pants', 'skirt'].includes(pending.input.bottom_kind)
      || (pending.input.fit_profile != null && typeof pending.input.fit_profile !== 'object')
      || (pending.input.view_mode != null && !['front_side', 'front_side_back'].includes(pending.input.view_mode))) throw new Error();
    return { pending, error: '' };
  } catch {
    return { pending: null, error: '저장된 단일 파츠 요청을 읽을 수 없습니다. 기존 요청 기록을 확인해야 새 생성을 접수할 수 있습니다.' };
  }
}
function clearSinglePart(key: string) {
  if (singlePartRecovery().pending?.key === key) localStorage.removeItem(singlePartPendingKey);
}
export const studioApi = {
  expressions: (job: string, version: string, signal?: AbortSignal) => request<ExpressionLibrary>(`/api/studio/bodies/${job}/${version}/expressions`, {signal}),
  applyExpressionOverlay: (job: string, version: string, input: { asset_id: string; name: ExpressionName }) => request<Expression>(`/api/studio/bodies/${job}/${version}/expressions/overlay`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(input),timeoutMs:60000}),
  bakeExpression: (job: string, version: string, generation: string) => request<Expression>(`/api/studio/bodies/${job}/${version}/expression-generations/${generation}/bake`, {method:'POST', timeoutMs:60000}),
  selectExpression: (job: string, version: string, expression_id: string | null, revision: string) => request<{selected:string|null;revision:string}>(`/api/studio/bodies/${job}/${version}/expressions/selection`, {method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({expression_id,revision})}),
  animals: (signal?: AbortSignal) => request<{items:Animal[]}>('/api/studio/animals',{signal}),
  uploadAnimal: (file:File,species:string,name:string) => request<Animal>(`/api/studio/animals?${new URLSearchParams({species,name})}`,{method:'POST',headers:{'Content-Type':'model/gltf-binary'},body:file,timeoutMs:60000}),
  rigAnimal: (id:string) => request<Animal>(`/api/studio/animals/${id}/rig`,{method:'POST'}),
  catalog: (signal?: AbortSignal) => request<Catalog>('/api/studio/catalog', { signal }),
  setVisibility: (id: string, scope: 'character' | 'version', deleted: boolean, revision: string) => request<Catalog>(`/api/studio/catalog/${id}/visibility`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json', 'If-Match': revision }, body: JSON.stringify({ scope, deleted }),
  }),
  saveMetadata: (id: string, name: string, archived: boolean, revision: string) => request<Catalog>(`/api/studio/catalog/${id}`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json', 'If-Match': revision }, body: JSON.stringify({ name, archived }),
  }),
  savePartMetadata: (id: string, slot: string, changes: PartMetadata, revision: string) => request<Catalog>(`/api/studio/catalog/${id}/parts/${slot}`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json', 'If-Match': revision }, body: JSON.stringify(changes),
  }),
  variantRecovery,
  singlePartRecovery,
  async singlePart(input: SinglePartInput) {
    const recovery = singlePartRecovery();
    if (recovery.error) throw new Error(recovery.error);
    const pending = recovery.pending || { key: crypto.randomUUID(), input };
    localStorage.setItem(singlePartPendingKey, JSON.stringify(pending));
    try {
      const result = await request<FactoryJob>('/api/avatar-factory/variants/single-part', { method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Idempotency-Key': pending.key }, body: JSON.stringify(pending.input) });
      clearSinglePart(pending.key); return result;
    } catch (e) {
      if (isDefinitiveRejection(e)) clearSinglePart(pending.key);
      throw e;
    }
  },
  async variant(input: VariantInput) {
    const recovery = variantRecovery();
    if (recovery.error) throw new Error(recovery.error);
    const pending = recovery.pending || { key: crypto.randomUUID(), input };
    localStorage.setItem(pendingKey, JSON.stringify(pending));
    try {
      const result = await request<FactoryJob>('/api/avatar-factory/variants', { method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Idempotency-Key': pending.key }, body: JSON.stringify(pending.input) });
      clearVariant(pending.key); return result;
    } catch (e) {
      if (isDefinitiveRejection(e)) clearVariant(pending.key);
      throw e;
    }
  },
  textures: (signal?: AbortSignal) => request<{ items: Tile[] }>('/api/studio/textures', { signal }),
  texture: (input: { surface: string; size: number; seed: number }) => request<Tile>('/api/studio/textures', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(input),
  }),
};
