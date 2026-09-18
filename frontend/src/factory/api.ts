import { request } from '../api';
import type { AvatarState } from '../avatar/core/types';

export type FaceSelection = { node_index: number; primitive_index: number; role: string; faces: number[] };
export type ImageRetry = { slot: string; view: string; failure_id: string };
export type FactoryJob = {
  id: string; character_id: string; character_name: string; source_sha256: string;
  status: string; created_at: string; error?: string; model_sha256?: string;
  updated_at?: string;
  character_flow?: { status: string; stage: string; message: string; busy: boolean };
  production_spec?: { id: string; sha256: string; body_height_m: number; generated_views: string[] };
  production_progress?: { percent: number; completed: number; total: number; current: string; status: string; message: string;
    updated_at?: string; spec_id?: string; images_received?: number; images_total?: number;
    steps: { id: string; label: string; state: string; percent: number | null; completed: number; total: number }[] };
  progress: { stage: string; message: string }; outfit?: AvatarState;
  profile?: { id: string; name: string; rig: string; head_ratio: number };
  technical?: { passed: boolean; bone_count: number; parts: number; source_preserved: boolean; file_bytes?: number; texture_pixels?: number; resource_warnings?: string[] };
  artifacts: { name: string; url: string }[];
  evidence?: { segmentation: string; source_triangles: number; part_triangles: Record<string, number>; limitations: string[] };
  input_kind?: string;
  production_mode?: 'legacy' | 'character_parts';
  image_provider?: string; image_model?: string;
  parts?: { slot: string; image_status: string; image_asset?: string; model_status: string; task_id?: string; progress?: number; image_failure?: { id: string; category: string }; views?: Record<string, {status: string; file?: string; qc?: {passed: boolean; issues: string[]}; failure?: {id: string; message?: string; elapsed_seconds?: number}}> }[];
  limits?: { image_tasks: number; meshy_tasks: number };
  next_actions?: { id: string; enabled: boolean; reason?: string; slot?: string; view?: string; failure_id?: string; images?: ImageRetry[] }[];
};
export type ImageProductionInput = { character_id: string; source_sha256: string; blueprint_revision: string; image_mode: 'generate' | 'prepared'; slots: string[]; production_mode?: 'legacy' | 'character_parts'; view_mode?: 'single' | 'front_side'; hair_length?: 'source' | 'short' | 'long'; reuse_job_id?: string; rig_with_meshy?: boolean; body_purpose?: 'whole_character' | 'wardrobe_base'; motion_actions?: Record<string, number> };
export type FactoryCapabilities = { character_pipeline?: string; ready: boolean; image_provider: string; image_model: string; slots: string[]; meshy_model: string; image_configured: boolean; meshy_configured: boolean; blender_available: boolean; next_actions: { id: string; enabled: boolean; reason?: string }[] };
export type ProductionInput = { character_id: string; source_sha256: string; selections: FaceSelection[] };
export type MeshyAction = { action_id: number; name: string; key: string; category: string; sub_category: string; preview_url?: string };
export type MeshyState = { provider: 'meshy'; status: string; rig_task_id?: string; progress: number; busy: boolean; error?: string;
  version?: string; model_sha256?: string; bone_count?: number; can_resume: boolean; artifacts: {name: string; url: string}[];
  clips: {slot: string; source: string; action_id: number | null}[]; selected: Record<string, number>;
  actions: {action_id: number; task_id?: string; status?: string; progress?: number}[] };
export type NativePartsState = {
  status: string; version?: string; error?: string; bone_count?: number; visual_review?: string;
  fitting_revision?: string; fit_update_available?: boolean;
  parts: { slot: string; objects: string[] }[];
  artifacts: { name: string; url: string; sha256: string }[];
};
export type NativeOutfit = { version: string; body_sha256: string; revision: string; slots: string[]; saved_at?: string };
export type FactoryStage = 'images' | 'models' | 'rig' | 'assemble';
export type FactoryStages = {
  busy: boolean; recommended_stage: FactoryStage | null;
  actions: { stage: FactoryStage; enabled: boolean; reason: string | null; paid: boolean }[];
  saved: { images: number; images_total: number; models: number; models_total: number; rig: boolean };
  operation: { id: string; stage: FactoryStage; status: string; error: string | null; created_at: string; updated_at: string } | null;
};
const pendingKey = 'gaesup.factory.pending.v1';
const imagePendingKey = (id: string) => `gaesup.image-production:${id}`;
const definitiveRejection = (error: unknown) => typeof error === 'object' && error && 'status' in error
  && [400, 401, 403, 404, 422].includes(Number(error.status));

export const factoryApi = {
  nativeParts: (id: string, signal?: AbortSignal) => request<NativePartsState>(`/api/avatar-factory/jobs/${id}/native-parts`, { signal }),
  assemble: (id: string, canonicalPose = false) => request<NativePartsState>(`/api/avatar-factory/jobs/${id}/native-parts?canonical_pose=${canonicalPose}`, { method: 'POST' }),
  nativeOutfit: (id: string, version: string) => request<NativeOutfit>(`/api/avatar-factory/jobs/${id}/native-outfits/${version}`),
  saveNativeOutfit: (id: string, version: string, input: Pick<NativeOutfit, 'body_sha256' | 'slots'>, revision: string, key: string) =>
    request<NativeOutfit>(`/api/avatar-factory/jobs/${id}/native-outfits/${version}`, { method: 'PUT',
      headers: { 'Content-Type': 'application/json', 'If-Match': revision, 'Idempotency-Key': key }, body: JSON.stringify(input) }),
  motionLibrary: () => request<{items: MeshyAction[]}>('/api/avatar-factory/motion-library'),
  motionDefaults: (jobId?: string) => request<{selections: Record<string, number>}>(jobId ? `/api/avatar-factory/jobs/${jobId}/motion-defaults` : '/api/avatar-factory/motion-defaults'),
  saveMotionDefaults: (selections: Record<string, number>, jobId?: string) => request<{selections: Record<string, number>}>(jobId ? `/api/avatar-factory/jobs/${jobId}/motion-defaults` : '/api/avatar-factory/motion-defaults', {method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({selections})}),
  meshy: (id: string) => request<MeshyState>(`/api/avatar-factory/jobs/${id}/meshy`),
  meshyRig: (id: string) => request<MeshyState>(`/api/avatar-factory/jobs/${id}/meshy/rig`, {method:'POST'}),
  meshyRecover: (id: string, task_id: string, action_id?: number) => request<MeshyState>(`/api/avatar-factory/jobs/${id}/meshy/recover`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({task_id,action_id})}),
  meshyAction: (id: string, slot: string, action_id: number) => request<MeshyState>(`/api/avatar-factory/jobs/${id}/meshy/actions`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({slot,action_id})}),
  rebuild: (id: string) => request<FactoryJob>(`/api/avatar-factory/jobs/${id}/rebuild`, { method: 'POST' }),
  capabilities: (signal?: AbortSignal) => request<FactoryCapabilities>('/api/avatar-factory/capabilities', { signal }),
  resume: (id: string) => request<FactoryJob>(`/api/avatar-factory/jobs/${id}/resume`, { method: 'POST' }),
  stages: (id: string, signal?: AbortSignal) => request<FactoryStages>(`/api/avatar-factory/jobs/${id}/stages`, { signal }),
  resumeStage: (id: string, stage: FactoryStage, key: string) => request<FactoryStages>(`/api/avatar-factory/jobs/${id}/stages/${stage}/resume`, {
    method: 'POST', headers: { 'Idempotency-Key': key },
  }),
  retryImage: (id: string, slot: string, view: string, failure_id: string) => request<FactoryJob>(`/api/avatar-factory/jobs/${id}/retry-image`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ slot, view, failure_id }),
  }),
  retryImages: (id: string, images: ImageRetry[]) => request<FactoryJob>(`/api/avatar-factory/jobs/${id}/retry-images`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ images }),
  }),
  recoverPart: (id:string,slot:string,task_id:string) => request<FactoryJob>(`/api/avatar-factory/jobs/${id}/recover-task`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({slot,task_id})}),
  pendingImage: (id: string): {key:string;input:ImageProductionInput}|null => {
    const key = imagePendingKey(id);
    const saved = localStorage.getItem(key) || sessionStorage.getItem(key);
    if (saved && !localStorage.getItem(key)) localStorage.setItem(key, saved);
    return JSON.parse(saved || 'null');
  },
  async produceImage(input: ImageProductionInput): Promise<FactoryJob> {
    const storage = imagePendingKey(input.character_id);
    const pending = factoryApi.pendingImage(input.character_id)||{key:crypto.randomUUID(),input};
    localStorage.setItem(storage,JSON.stringify(pending));
    try {
      const job = await request<FactoryJob>('/api/avatar-factory/image-jobs',{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':pending.key},body:JSON.stringify(pending.input)});
      localStorage.removeItem(storage); sessionStorage.removeItem(storage); return job;
    } catch(error) {
      if (definitiveRejection(error)) { localStorage.removeItem(storage); sessionStorage.removeItem(storage); }
      throw error;
    }
  },
  list: (signal?: AbortSignal) => request<{ jobs: FactoryJob[] }>('/api/avatar-factory/jobs', { signal }),
  pending: (): { key: string; input: ProductionInput } | null => JSON.parse(sessionStorage.getItem(pendingKey) || 'null'),
  async produce(input: ProductionInput): Promise<FactoryJob> {
    const pending = factoryApi.pending() || { key: crypto.randomUUID(), input };
    sessionStorage.setItem(pendingKey, JSON.stringify(pending));
    try {
      const job = await request<FactoryJob>('/api/avatar-factory/jobs', {
        method: 'POST', headers: { 'Content-Type': 'application/json', 'Idempotency-Key': pending.key }, body: JSON.stringify(pending.input),
      });
      sessionStorage.removeItem(pendingKey);
      return job;
    } catch (error) {
      if (typeof error === 'object' && error && 'status' in error && Number(error.status) >= 400 && Number(error.status) < 500)
        sessionStorage.removeItem(pendingKey);
      throw error;
    }
  },
};
