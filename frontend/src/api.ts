export type Part = { node_index: number; role: string; name?: string };
export type Operation = { id: string; action_id: string; status: string; error: { code: string; message: string } | null };
export type Character = {
  id: string; name: string; revision: string; height_meters: number | null;
  pipeline_status: string; rig_origin: string; model_id: string | null; model_sha256: string | null;
  provider: { stage: string | null; status: string | null; progress: number | null; task_id: string | null; http_status: number | null };
  operation: Operation | null;
  motion_pack: { status: string | null; submitted_tasks: number; max_new_tasks: number | null;
    clips: Record<string, { action_id: number | null; source: string }>;
    tasks: Record<string, { status: string; task_id: string | null; progress: number | null }> };
  problems: { code: string; message: string }[];
  next_actions: { id: string; label: string; enabled: boolean; reason: string | null; external_mutation: boolean }[];
  artifacts: { id: string; kind: string; bytes: number; url: string }[];
  inspection: { errors?: string[]; nodes?: { index: number; name: string; skinned: boolean }[]; metrics?: { vertices: number; triangles: number; joints: string[]; animations: string[] } };
  parts: Part[]; body_coverage: string;
  review: { decision?: string; notes?: string; reviewed_at?: string };
};

export class ApiError extends Error {
  constructor(public code: string, message: string, public status: number) { super(message); }
}

export async function request<T>(url: string, options: RequestInit = {}): Promise<T> {
  let response: Response;
  try { response = await fetch(url, options); }
  catch { throw new ApiError('connection', '백엔드에 연결할 수 없습니다. 연결이 복구되면 다시 동기화합니다.', 0); }
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const validation = Array.isArray(body.detail) ? body.detail.map((item: { loc?: string[]; msg?: string }) => `${item.loc?.slice(1).join('.') || '입력'}: ${item.msg || '값 확인 필요'}`).join(' / ') : typeof body.detail === 'string' && body.detail !== 'Not Found' ? body.detail : '';
    const fallback = response.status === 401 ? 'API 인증이 필요합니다. 로컬 서버 설정을 확인해 주세요.' : response.status === 404 ? 'API 또는 자료를 찾을 수 없습니다. 프론트와 백엔드 버전·연결 주소를 확인해 주세요.' : response.status >= 500 ? `서버 오류 (${response.status}). 저장된 작업은 다시 불러와 확인할 수 있습니다.` : `요청 오류 (${response.status}). 입력을 확인해 주세요.`;
    throw new ApiError(body.error?.code || 'request_failed', body.error?.message || validation || fallback, response.status);
  }
  return body as T;
}

const endpoint = (id: string) => `/api/characters/${encodeURIComponent(id)}`;
export const api = {
  list: () => request<{ characters: Character[] }>('/api/characters'),
  detail: (id: string) => request<Character>(endpoint(id)),
  create: (name: string, height: number | null) => request<Character>('/api/characters', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name, height_meters: height }) }),
  update: (c: Character, name: string, height: number | null) => request<Character>(endpoint(c.id), { method: 'PATCH', headers: { 'Content-Type': 'application/json', 'If-Match': c.revision }, body: JSON.stringify({ name, height_meters: height }) }),
  upload: (c: Character, file: File, kind: string) => request<Character>(`${endpoint(c.id)}/sources?kind=${kind}`, { method: 'POST', headers: { 'If-Match': c.revision, 'Content-Type': file.type || 'application/octet-stream' }, body: file }),
  action: (c: Character, action: string, payload: object, key: string) => request<{ operation: Operation }>(`${endpoint(c.id)}/actions/${action}`, { method: 'POST', headers: { 'If-Match': c.revision, 'Idempotency-Key': key, 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }),
  recover: (c: Character) => request<{ operation: Operation }>(`${endpoint(c.id)}/operations/${c.operation!.id}/recover`, { method: 'POST', headers: { 'If-Match': c.revision } }),
};
