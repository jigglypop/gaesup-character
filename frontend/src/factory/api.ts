import { request } from '../api';
import type { AvatarState } from '../avatar/core/types';

export type FaceSelection = { node_index: number; primitive_index: number; role: string; faces: number[] };
export type FactoryJob = {
  id: string; character_id: string; character_name: string; source_sha256: string;
  status: string; created_at: string; error?: string; model_sha256?: string;
  progress: { stage: string; message: string }; outfit?: AvatarState;
  profile?: { id: string; name: string; rig: string; head_ratio: number };
  technical?: { passed: boolean; bone_count: number; parts: number; source_preserved: boolean; file_bytes?: number; texture_pixels?: number; resource_warnings?: string[] };
  artifacts: { name: string; url: string }[];
  evidence?: { segmentation: string; source_triangles: number; part_triangles: Record<string, number>; limitations: string[] };
  input_kind?: string;
  production_mode?: 'legacy' | 'character_parts';
  image_provider?: string; image_model?: string;
  parts?: { slot: string; image_status: string; image_asset?: string; model_status: string; task_id?: string; progress?: number }[];
  limits?: { image_tasks: number; meshy_tasks: number };
  next_actions?: { id: string; enabled: boolean; reason?: string }[];
};
export type ImageProductionInput = { character_id: string; source_sha256: string; blueprint_revision: string; image_mode: 'generate' | 'prepared'; slots: string[]; production_mode?: 'legacy' | 'character_parts'; reuse_job_id?: string; rig_with_meshy?: boolean; body_purpose?: 'whole_character' | 'wardrobe_base'; motion_actions?: Record<string, number> };
export type FactoryCapabilities = { ready: boolean; image_provider: string; image_model: string; slots: string[]; meshy_model: string; image_configured: boolean; meshy_configured: boolean; blender_available: boolean; next_actions: { id: string; enabled: boolean; reason?: string }[] };
export type ProductionInput = { character_id: string; source_sha256: string; selections: FaceSelection[] };
export type MeshyAction = { action_id: number; name: string; key: string; category: string; sub_category: string; preview_url?: string };
export type MeshyState = { provider: 'meshy'; status: string; rig_task_id?: string; progress: number; busy: boolean; error?: string;
  version?: string; model_sha256?: string; bone_count?: number; can_resume: boolean; artifacts: {name: string; url: string}[];
  clips: {slot: string; source: string; action_id: number | null}[]; selected: Record<string, number>;
  actions: {action_id: number; task_id?: string; status?: string; progress?: number}[] };
const pendingKey = 'gaesup.factory.pending.v1';

export const factoryApi = {
  motionLibrary: () => request<{items: MeshyAction[]}>('/api/avatar-factory/motion-library'),
  motionDefaults: () => request<{selections: Record<string, number>}>('/api/avatar-factory/motion-defaults'),
  saveMotionDefaults: (selections: Record<string, number>) => request<{selections: Record<string, number>}>('/api/avatar-factory/motion-defaults', {method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({selections})}),
  meshy: (id: string) => request<MeshyState>(`/api/avatar-factory/jobs/${id}/meshy`),
  meshyRig: (id: string) => request<MeshyState>(`/api/avatar-factory/jobs/${id}/meshy/rig`, {method:'POST'}),
  meshyRecover: (id: string, task_id: string, action_id?: number) => request<MeshyState>(`/api/avatar-factory/jobs/${id}/meshy/recover`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({task_id,action_id})}),
  meshyAction: (id: string, slot: string, action_id: number) => request<MeshyState>(`/api/avatar-factory/jobs/${id}/meshy/actions`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({slot,action_id})}),
  rebuild: (id: string) => request<FactoryJob>(`/api/avatar-factory/jobs/${id}/rebuild`, { method: 'POST' }),
  capabilities: () => request<FactoryCapabilities>('/api/avatar-factory/capabilities'),
  resume: (id: string) => request<FactoryJob>(`/api/avatar-factory/jobs/${id}/resume`, { method: 'POST' }),
  recoverPart: (id:string,slot:string,task_id:string) => request<FactoryJob>(`/api/avatar-factory/jobs/${id}/recover-task`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({slot,task_id})}),
  pendingImage: (id: string): {key:string;input:ImageProductionInput}|null => JSON.parse(sessionStorage.getItem(`gaesup.image-production:${id}`)||'null'),
  async produceImage(input: ImageProductionInput): Promise<FactoryJob> {
    const storage = `gaesup.image-production:${input.character_id}`;
    const pending = factoryApi.pendingImage(input.character_id)||{key:crypto.randomUUID(),input};
    sessionStorage.setItem(storage,JSON.stringify(pending));
    try {
      const job = await request<FactoryJob>('/api/avatar-factory/image-jobs',{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':pending.key},body:JSON.stringify(pending.input)});
      sessionStorage.removeItem(storage); return job;
    } catch(error) {
      if(typeof error==='object'&&error&&'status' in error&&Number(error.status)>=400&&Number(error.status)<500)sessionStorage.removeItem(storage);
      throw error;
    }
  },
  list: () => request<{ jobs: FactoryJob[] }>('/api/avatar-factory/jobs'),
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
