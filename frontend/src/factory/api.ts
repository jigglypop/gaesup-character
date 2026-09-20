import { isDefinitiveRejection, request } from '../api';
import type { AvatarState } from '../avatar/core/types';
import type { MeshyOptions } from '../studio/meshy-options';

export type ImageRetry = { slot: string; view: string; failure_id: string };
export type FitAnchor = { name: string; source: [number, number, number]; target?: [number, number, number] };
export type FitProfile = {
  revision?: 'garment-fit-v1';
  sleeve?: 'source' | 'none' | 'short' | 'long';
  kind?: 'source' | 'pants' | 'skirt';
  ease?: 'source' | 'regular' | 'loose';
  region_ease?: Partial<Record<'torso' | 'sleeve' | 'hip', 'source' | 'regular' | 'loose'>>;
  length_ratio?: number | null;
  sleeve_ratio?: number | null;
  anchors?: FitAnchor[];
  source_sha256?: string;
};
export type FactoryJob = {
  meshy_options?: Record<string, MeshyOptions>;
  id: string; character_id: string; character_name: string; source_sha256: string;
  status: string; created_at: string; error?: string; model_sha256?: string;
  base_job_id?: string; base_version?: string; requested_slots?: string[];
  base_body?: { body_type: 'male' | 'female'; import_mode?: 'register' | 'rig'; views?: Partial<Record<'front' | 'side' | 'back', string>>; rig_source?: { job_id: string; version: string } | null };
  assembly_version?: string | null;
  assembly_artifacts?: { name: string; url: string; sha256: string }[];
  updated_at?: string;
  character_flow?: { status: string; stage: string; message: string; busy: boolean };
  production_spec?: { id: string; sha256: string; body_height_m: number; generated_views: string[] };
  reference_preparation?: { status: string; revision: string; file?: string; sha256?: string; raw_file?: string; failure?: { message?: string };
    views?: Record<string, { status: string; file?: string; sha256?: string; raw_file?: string; failure?: { message?: string } }> };
  production_progress?: { percent: number; completed: number; total: number; current: string; status: string; message: string;
    updated_at?: string; spec_id?: string; images_received?: number; images_total?: number;
    steps: { id: string; label: string; state: string; percent: number | null; completed: number; total: number }[] };
  progress: { stage: string; message: string }; outfit?: AvatarState;
  profile?: { id: string; name: string; rig: string; head_ratio: number };
  technical?: { passed: boolean; bone_count: number; parts: number; source_preserved: boolean; file_bytes?: number; texture_pixels?: number; resource_warnings?: string[] };
  artifacts: { name: string; url: string; sha256?: string }[];
  evidence?: { segmentation: string; source_triangles: number; part_triangles: Record<string, number>; limitations: string[] };
  input_kind?: string;
  production_mode?: 'legacy' | 'character_parts';
  image_provider?: string; image_model?: string;
  parts?: { slot: string; image_status: string; image_asset?: string; model_status: string; task_id?: string; progress?: number; reused?: boolean; assembly_status?: 'pending' | 'running' | 'failed' | 'complete'; image_failure?: { id: string; category: string }; views?: Record<string, {status: string; file?: string; qc?: {passed: boolean; issues: string[]}; failure?: {id: string; message?: string; elapsed_seconds?: number}}> }[];
  limits?: { image_tasks: number; meshy_tasks: number; reference_tasks?: number; expression_tasks?: number };
  next_actions?: { id: string; enabled: boolean; reason?: string; slot?: string; view?: string; failure_id?: string; images?: ImageRetry[] }[];
};
export type ImageProductionInput = { meshy_options?: MeshyOptions; character_id: string; source_sha256: string; blueprint_revision: string; image_mode: 'generate' | 'prepared'; slots: string[]; production_mode?: 'legacy' | 'character_parts'; view_mode?: 'single' | 'front_side' | 'front_side_back'; hair_length?: 'source' | 'short' | 'long'; reuse_job_id?: string; rig_with_meshy?: boolean; body_purpose?: 'whole_character' | 'wardrobe_base'; motion_actions?: Record<string, number>; design_prompts?: Record<string, string>; prepare_reference?: boolean; default_expressions?: boolean; base_job_id?: string; base_version?: string; fit_profiles?: { top?: FitProfile; bottom?: FitProfile } };
export type FactoryCapabilities = { character_pipeline?: string; ready: boolean; image_provider: string; image_model: string; slots: string[]; design_prompt_defaults?: Record<string, string>; meshy_model: string; image_configured: boolean; meshy_configured: boolean; blender_available: boolean; next_actions: { id: string; enabled: boolean; reason?: string }[] };
export type MeshyAction = { action_id: number; name: string; key: string; category: string; sub_category: string; preview_url?: string };
export type MeshyState = { provider: 'meshy'; status: string; rig_task_id?: string; progress: number; busy: boolean; error?: string;
  origin?: string; can_request_action?: boolean;
  version?: string; model_sha256?: string; bone_count?: number; can_resume: boolean; artifacts: {name: string; url: string}[];
  clips: {slot: string; source: string; action_id: number | null}[]; selected: Record<string, number>;
  actions: {action_id: number; task_id?: string; status?: string; progress?: number}[] };
export type NativePartsState = {
  origin?: string;
  rigged?: boolean;
  status: string; version?: string; error?: string; bone_count?: number; visual_review?: string;
  fitting_revision?: string; fit_update_available?: boolean; expression_pending?: boolean; fit_status?: string;
  refit_request_key?: string | null;
  incomplete_parts?: { slot: string; status: string; errors: { code: string; message: string }[] }[];
  parts: { slot: string; objects: string[]; runtime_budget?: {
    source_triangles?: number; runtime_triangles?: number; target_triangles?: number;
    texture_max_edge?: number; resized_textures?: number; source_files_preserved?: boolean;
  } }[];
  artifacts: { name: string; url: string; sha256: string }[];
  preview?: NativePartsState;
};
export type NativeOutfit = { version: string; body_sha256: string; revision: string; slots: string[]; hair_color?: string | null; saved_at?: string };
export type BodyProfileState = { revision: string; body: null | { job_id: string; version: string; profile_id: string; body_sha256: string } };
export type PartFitProfile = { slot: 'top' | 'bottom'; source_version: string; source_sha256: string; fit_profile: FitProfile; measurement?: Record<string, unknown>; body_profile?: Record<string, unknown> };
export type NativePartsVersions = { current: string | null; items: { version: string; created_at?: string; fitting_revision?: string; url?: string }[] };
export type FactoryStage = 'images' | 'models' | 'rig' | 'assemble' | 'expressions';
export type FactoryStages = {
  busy: boolean; recommended_stage: FactoryStage | null;
  actions: { stage: FactoryStage; enabled: boolean; reason: string | null; paid: boolean }[];
  saved: { images: number; images_total: number; models: number; models_total: number; rig: boolean };
  operation: { id: string; stage: FactoryStage; status: string; error: string | null; created_at: string; updated_at: string } | null;
};
export type RigTransferInput = { source_job_id: string; source_version: string };
export type RigTransferState = {
  status: 'not_started' | 'accepted' | 'running' | 'paused' | 'complete'; can_start: boolean; error?: string;
  source_job_id?: string; source_version?: string; id?: string; request_key?: string;
  recommended_source?: RigTransferSource | null;
};
export type RigTransferSource = { job_id: string; version: string; name: string };
const imagePendingKey = (id: string) => `gaesup.image-production:${id}`;
const nativePartsSelectionKey = (id: string) => `gaesup.native-parts-selection:${id}`;
export type PendingNativePartsSelection = { key: string; input: { version: string; expected_version: string } };
export const factoryApi = {
  nativeParts: (id: string, signal?: AbortSignal) => request<NativePartsState>(`/api/avatar-factory/jobs/${id}/native-parts`, { signal }),
  assemble: (id: string, canonicalPose = false) => request<NativePartsState>(`/api/avatar-factory/jobs/${id}/native-parts?canonical_pose=${canonicalPose}`, { method: 'POST' }),
  nativeOutfit: (id: string, version: string) => request<NativeOutfit>(`/api/avatar-factory/jobs/${id}/native-outfits/${version}`),
  saveNativeOutfit: (id: string, version: string, input: Pick<NativeOutfit, 'body_sha256' | 'slots' | 'hair_color'>, revision: string, key: string) =>
    request<NativeOutfit>(`/api/avatar-factory/jobs/${id}/native-outfits/${version}`, { method: 'PUT',
      headers: { 'Content-Type': 'application/json', 'If-Match': revision, 'Idempotency-Key': key }, body: JSON.stringify(input) }),
  motionLibrary: (signal?: AbortSignal) => request<{items: MeshyAction[]}>('/api/avatar-factory/motion-library', { signal }),
  motionDefaults: (jobId?: string, signal?: AbortSignal) => request<{selections: Record<string, number>}>(jobId ? `/api/avatar-factory/jobs/${jobId}/motion-defaults` : '/api/avatar-factory/motion-defaults', { signal }),
  saveMotionDefaults: (selections: Record<string, number>, jobId?: string) => request<{selections: Record<string, number>}>(jobId ? `/api/avatar-factory/jobs/${jobId}/motion-defaults` : '/api/avatar-factory/motion-defaults', {method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({selections})}),
  meshy: (id: string, signal?: AbortSignal) => request<MeshyState>(`/api/avatar-factory/jobs/${id}/meshy`, {signal}),
  meshyRig: (id: string) => request<MeshyState>(`/api/avatar-factory/jobs/${id}/meshy/rig`, {method:'POST'}),
  meshyRecover: (id: string, task_id: string, action_id?: number) => request<MeshyState>(`/api/avatar-factory/jobs/${id}/meshy/recover`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({task_id,action_id})}),
  meshyAction: (id: string, slot: string, action_id: number) => request<MeshyState>(`/api/avatar-factory/jobs/${id}/meshy/actions`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({slot,action_id})}),
  capabilities: (signal?: AbortSignal) => request<FactoryCapabilities>('/api/avatar-factory/capabilities', { signal }),
  stages: (id: string, signal?: AbortSignal) => request<FactoryStages>(`/api/avatar-factory/jobs/${id}/stages`, { signal }),
  bodyProfile: (signal?: AbortSignal) => request<BodyProfileState>('/api/avatar-factory/body-profile', { signal }),
  saveBodyProfile: (job_id: string, version: string, expected_revision: string) => request<BodyProfileState>('/api/avatar-factory/body-profile', {
    method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ job_id, version, expected_revision }),
  }),
  fitProfile: (id: string, slot: 'top' | 'bottom', sourceVersion: string, signal?: AbortSignal) => request<PartFitProfile>(`/api/avatar-factory/jobs/${id}/fit-profile/${slot}?${new URLSearchParams({ source_version: sourceVersion })}`, { signal }),
  nativePartsVersions: (id: string, signal?: AbortSignal) => request<NativePartsVersions>(`/api/avatar-factory/jobs/${id}/native-parts/versions`, { signal }),
  pendingNativePartsSelection: (id: string): PendingNativePartsSelection | null => {
    const raw = localStorage.getItem(nativePartsSelectionKey(id));
    if (!raw) return null;
    const value = JSON.parse(raw) as PendingNativePartsSelection;
    if (typeof value?.key !== 'string' || !value.key || typeof value.input?.version !== 'string'
      || typeof value.input?.expected_version !== 'string') throw new Error('저장된 버전 전환 요청을 확인할 수 없습니다.');
    return value;
  },
  async selectNativePartsVersion(id: string, version: string, expected_version: string) {
    const storage = nativePartsSelectionKey(id);
    const pending = factoryApi.pendingNativePartsSelection(id) || { key: crypto.randomUUID(), input: { version, expected_version } };
    localStorage.setItem(storage, JSON.stringify(pending));
    try {
      const result = await request<NativePartsState>(`/api/avatar-factory/jobs/${id}/native-parts/select`, {
        method: 'POST', headers: { 'Content-Type': 'application/json', 'Idempotency-Key': pending.key }, body: JSON.stringify(pending.input),
      });
      localStorage.removeItem(storage); return result;
    } catch (error) {
      if (isDefinitiveRejection(error)) localStorage.removeItem(storage);
      throw error;
    }
  },
  pendingRefit: (id: string): { key: string; input: { source_version: string; slot: string; fit_profile?: FitProfile } } | null => {
    const raw = localStorage.getItem(`gaesup.part-refit:${id}`);
    if (!raw) return null;
    const value = JSON.parse(raw);
    if (typeof value?.key !== 'string' || typeof value?.input?.source_version !== 'string' || typeof value?.input?.slot !== 'string') throw new Error('저장된 피팅 요청을 확인할 수 없습니다.');
    return value;
  },
  acknowledgeRefit: (id: string, key: string) => {
    if (factoryApi.pendingRefit(id)?.key === key) localStorage.removeItem(`gaesup.part-refit:${id}`);
  },
  async refitPart(id: string, source_version: string, slot: string, fit_profile?: FitProfile) {
    const storage = `gaesup.part-refit:${id}`;
    const saved = factoryApi.pendingRefit(id);
    if (saved && saved.input.slot !== slot) throw new Error(`저장된 ${saved.input.slot} 피팅 요청을 먼저 복구해야 합니다.`);
    const pending = saved || { key: crypto.randomUUID(), input: { source_version, slot, ...(fit_profile ? { fit_profile } : {}) } };
    localStorage.setItem(storage, JSON.stringify(pending));
    try {
      const result = await request<NativePartsState>(`/api/avatar-factory/jobs/${id}/native-parts/refit`, {
        method: 'POST', headers: { 'Content-Type': 'application/json', 'Idempotency-Key': pending.key }, body: JSON.stringify(pending.input),
      });
      localStorage.removeItem(storage); return result;
    } catch (error) {
      if (isDefinitiveRejection(error)) localStorage.removeItem(storage);
      throw error;
    }
  },
  resumeStage: (id: string, stage: FactoryStage, key: string) => request<FactoryStages>(`/api/avatar-factory/jobs/${id}/stages/${stage}/resume`, {
    method: 'POST', headers: { 'Idempotency-Key': key },
  }),
  rigTransfer: (id: string, signal?: AbortSignal) => request<RigTransferState>(`/api/avatar-factory/jobs/${id}/rig-transfer`, { signal }),
  rigTransferSources: (signal?: AbortSignal) => request<{items: RigTransferSource[]}>('/api/avatar-factory/rig-transfer/sources', { signal, timeoutMs: 30000 }),
  startRigTransfer: (id: string, input: RigTransferInput, key: string) => request<RigTransferState>(`/api/avatar-factory/jobs/${id}/rig-transfer`, {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'Idempotency-Key': key }, body: JSON.stringify(input),
  }),
  retryImages: (id: string, images: ImageRetry[]) => request<FactoryJob>(`/api/avatar-factory/jobs/${id}/retry-images`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ images }),
  }),
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
      if (isDefinitiveRejection(error)) { localStorage.removeItem(storage); sessionStorage.removeItem(storage); }
      throw error;
    }
  },
  detail: (id: string, signal?: AbortSignal) => request<FactoryJob>(`/api/avatar-factory/jobs/${id}`, { signal }),
  list: (signal?: AbortSignal) => request<{ jobs: FactoryJob[] }>('/api/avatar-factory/jobs', { signal, timeoutMs: 60000 }),
};
