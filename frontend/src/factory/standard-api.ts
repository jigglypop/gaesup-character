import { request } from '../api';

export type StandardItem = {
  id: string; kind: 'base' | 'part' | 'assembly' | 'image' | 'shape' | 'design'; name: string; status: string;
  model_sha256?: string; error?: string; created_at: string;
  review?: { decision: string; notes?: string };
  contract: { base_id?: string; base_sha256?: string; slot?: string; height_m?: number; object_key?: string; view?: string; image_ids?: string[] };
  provider?: { task_id?: string; status?: string; progress?: number; model: string };
  result?: { height_m: number; bones: string[]; animations: string[]; bone_heads_gltf: Record<string, number[]>;
    materials?: { index: number; name: string; has_uv: boolean }[];
    part_materials?: { index: number; name: string; has_uv: boolean }[];
    model_asset?: string;
    image_asset?: string;
    fit: { uniform_scale?: number; anchor_errors_m?: number[]; max_surface_distance_m?: number; possible_inside_vertices?: number } };
  artifacts: { name: string; url: string; sha256: string }[]; next_actions: string[];
};

const pendingKey = 'gaesup.standard.pending.v1';
export type OutfitSelection = { base_id: string; base_sha256: string; revision: string; part_ids: string[]; saved_at?: string };
type PendingOutfit = { key: string; revision: string; input: { base_sha256: string; part_ids: string[] } };
const outfitKey = (base: string) => `gaesup.standard.outfit.pending.v1.${base}`;
export const outfitApi = {
  get: (base: string) => request<OutfitSelection>(`/api/avatar-standard/outfits/${base}`),
  pending: (base: string): PendingOutfit | null => JSON.parse(sessionStorage.getItem(outfitKey(base)) || 'null'),
  async save(base: string, revision: string, input: PendingOutfit['input']) {
    const pending = outfitApi.pending(base) || { key: crypto.randomUUID(), revision, input };
    sessionStorage.setItem(outfitKey(base), JSON.stringify(pending));
    try {
      const result = await request<OutfitSelection>(`/api/avatar-standard/outfits/${base}`, { method: 'PUT',
        headers: { 'Content-Type': 'application/json', 'If-Match': pending.revision, 'Idempotency-Key': pending.key }, body: JSON.stringify(pending.input) });
      sessionStorage.removeItem(outfitKey(base)); return result;
    } catch (error) {
      if (typeof error === 'object' && error && 'status' in error && Number(error.status) >= 400 && Number(error.status) < 500) sessionStorage.removeItem(outfitKey(base));
      throw error;
    }
  },
};
export type WardrobeRow = { key: string; name: string; slot: string; garment_type: string; description: string };
export type WardrobeBatch = {
  id: string; name: string; status: string; busy: boolean; can_resume: boolean; ready_count: number; error?: string;
  contract: { base_id: string; base_sha256: string; rows: WardrobeRow[]; reference_asset?: string | null };
  reference_image_url?: string | null;
  spec: { height_m: number; bones: string[] };
  limits: { images: number; meshy_generation: number; meshy_rigging: number; image_model: string; shape_model: string };
  rows: (WardrobeRow & { stage: string; image_id?: string; design?: StandardItem; shape?: StandardItem; part?: StandardItem; error?: string })[];
};

const batchPending = 'gaesup.wardrobe.batch.pending.v1';
export const batchApi = {
  list: () => request<{ items: WardrobeBatch[] }>('/api/avatar-standard/batches'),
  pending: () => sessionStorage.getItem(batchPending) !== null,
  async create(input?: unknown) {
    const stored = sessionStorage.getItem(batchPending);
    if (!stored && !input) throw new Error('복구할 배치 요청이 없습니다.');
    const pending = stored ? JSON.parse(stored) : { key: crypto.randomUUID(), input };
    sessionStorage.setItem(batchPending, JSON.stringify(pending));
    try {
      const result = await request<WardrobeBatch>('/api/avatar-standard/batches', { method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Idempotency-Key': pending.key }, body: JSON.stringify(pending.input) });
      sessionStorage.removeItem(batchPending); return result;
    } catch (error) {
      if (typeof error === 'object' && error && 'status' in error && Number(error.status) >= 400 && Number(error.status) < 500) sessionStorage.removeItem(batchPending);
      throw error;
    }
  },
  resume: (id: string) => request<WardrobeBatch>(`/api/avatar-standard/batches/${id}/resume`, { method: 'POST' }),
};

export const standardApi = {
  async captureReference(url: string) {
    const response = await fetch(url);
    if (!response.ok) throw new Error('참고할 원본 이미지를 불러올 수 없습니다.');
    let blob = await response.blob();
    if (blob.type !== 'image/png') {
      const bitmap = await createImageBitmap(blob);
      try {
        if (Math.max(bitmap.width, bitmap.height) > 4096) throw new Error('참고 이미지는 4096px 이하로 준비해 주세요.');
        const canvas = document.createElement('canvas'); canvas.width = bitmap.width; canvas.height = bitmap.height;
        canvas.getContext('2d')!.drawImage(bitmap, 0, 0);
        blob = await new Promise<Blob>((resolve, reject) => canvas.toBlob(value => value ? resolve(value) : reject(new Error('참고 이미지 PNG 저장 실패')), 'image/png'));
      } finally { bitmap.close(); }
    }
    return standardApi.upload(new File([blob], 'reference.png', { type: 'image/png' }), 'png');
  },
  list: () => request<{ items: StandardItem[] }>('/api/avatar-standard/items'),
  pending: (): { kind: string; key: string; input: unknown } | null => JSON.parse(sessionStorage.getItem(pendingKey) || 'null'),
  async create(kind: string, input: unknown) {
    const pending = standardApi.pending() || { kind, key: crypto.randomUUID(), input };
    sessionStorage.setItem(pendingKey, JSON.stringify(pending));
    try {
      const result = await request<StandardItem>(`/api/avatar-standard/${pending.kind}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json', 'Idempotency-Key': pending.key }, body: JSON.stringify(pending.input),
      });
      sessionStorage.removeItem(pendingKey); return result;
    } catch (error) {
      if (typeof error === 'object' && error && 'status' in error && Number(error.status) >= 400 && Number(error.status) < 500) sessionStorage.removeItem(pendingKey);
      throw error;
    }
  },
  upload: (file: File, kind: 'glb' | 'png') => request<{ id: string }>(`/api/avatar-standard/uploads/${kind}`, { method: 'POST', body: file }),
  image: (input: unknown) => request<StandardItem>('/api/avatar-standard/images', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(input) }),
  review: (id: string, input: unknown) => request<StandardItem>(`/api/avatar-standard/items/${id}/review`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(input) }),
  recover: (id: string) => request<StandardItem>(`/api/avatar-standard/items/${id}/recover`, { method: 'POST' }),
  poll: (id: string) => request<StandardItem>(`/api/avatar-standard/items/${id}/poll`, { method: 'POST' }),
  resumeSubmission: (id: string) => request<StandardItem>(`/api/avatar-standard/items/${id}/resume-submission`, { method: 'POST' }),
  recoverTask: (id: string, task_id: string) => request<StandardItem>(`/api/avatar-standard/items/${id}/recover-task`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ task_id }) }),
  resumeDesign: (id: string) => request<StandardItem>(`/api/avatar-standard/items/${id}/resume-design`, { method: 'POST' }),
  alignDesign: (id: string, input: unknown) => request<StandardItem>(`/api/avatar-standard/items/${id}/align-design`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(input) }),
};
