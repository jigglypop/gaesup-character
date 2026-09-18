import { request } from '../api';
import type { FactoryJob } from '../factory/api';
import type { ExpressionMap, ExpressionName, FaceLayout } from '../texture-expressions';

export type Catalog = { revision: string; items: Record<string, { name: string; archived: boolean }> };
export type VariantInput = { base_job_id: string; base_version: string; slots: string[]; hair_length: 'source' | 'short' | 'long'; descriptions: Record<string, string> };
export type Tile = { id: string; surface: string; size: number; seed: number; gpu: { estimated_bytes_with_mips: number }; artifacts: { name: string; url: string }[] };
export type Animal = {id:string;name:string;species:'dog'|'cat'|'dragon';status:string;error?:string;bones?:number;artifacts:{name:string;url:string}[]};
export type Expression = { id: string; name: Exclude<ExpressionName, 'neutral'>; layout: FaceLayout; materials: {material:number;file:string}[]; artifacts:{name:string;url:string;sha256:string}[] };
const pendingKey = 'gaesup.studio.variant.v1';
export const studioApi = {
  expressions: (job: string, version: string, signal?: AbortSignal) => request<{items: Expression[]}>(`/api/studio/bodies/${job}/${version}/expressions`, {signal}),
  saveExpression: (job: string, version: string, input: {body_sha256:string;name:Exclude<ExpressionName,'neutral'>;layout:FaceLayout;maps:ExpressionMap[]}) => request<Expression>(`/api/studio/bodies/${job}/${version}/expressions`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(input), timeoutMs:60000}),
  animals: (signal?: AbortSignal) => request<{items:Animal[]}>('/api/studio/animals',{signal}),
  uploadAnimal: (file:File,species:string,name:string) => request<Animal>(`/api/studio/animals?${new URLSearchParams({species,name})}`,{method:'POST',headers:{'Content-Type':'model/gltf-binary'},body:file,timeoutMs:60000}),
  rigAnimal: (id:string) => request<Animal>(`/api/studio/animals/${id}/rig`,{method:'POST'}),
  catalog: (signal?: AbortSignal) => request<Catalog>('/api/studio/catalog', { signal }),
  saveMetadata: (id: string, name: string, archived: boolean, revision: string) => request<Catalog>(`/api/studio/catalog/${id}`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json', 'If-Match': revision }, body: JSON.stringify({ name, archived }),
  }),
  pendingVariant: (): { key: string; input: VariantInput } | null => JSON.parse(localStorage.getItem(pendingKey) || 'null'),
  async variant(input: VariantInput) {
    const pending = studioApi.pendingVariant() || { key: crypto.randomUUID(), input };
    localStorage.setItem(pendingKey, JSON.stringify(pending));
    try {
      const result = await request<FactoryJob>('/api/avatar-factory/variants', { method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Idempotency-Key': pending.key }, body: JSON.stringify(pending.input) });
      localStorage.removeItem(pendingKey); return result;
    } catch (e) {
      if (typeof e === 'object' && e && 'status' in e && [400, 401, 403, 404, 422].includes(Number(e.status))) localStorage.removeItem(pendingKey);
      throw e;
    }
  },
  textures: (signal?: AbortSignal) => request<{ items: Tile[] }>('/api/studio/textures', { signal }),
  texture: (input: { surface: string; size: number; seed: number }) => request<Tile>('/api/studio/textures', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(input),
  }),
};
