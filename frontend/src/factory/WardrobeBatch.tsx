import { useEffect, useRef, useState } from 'react';
import { type Character } from '../api';
import { batchApi, standardApi, type StandardItem, type WardrobeBatch as Batch, type WardrobeRow } from './standard-api';

const slots: Record<string, string> = { top: '상의', bottom: '하의', shoeLeft: '왼쪽 신발', shoeRight: '오른쪽 신발', hair: '헤어', hat: '모자', accessory: '장식' };
const stages: Record<string, string> = { design: '시안 생성', image_review: '착용점 정렬 필요', image_ready: '3D 생성 준비', shape: 'Meshy 형상 생성', fit_required: '몸에 맞춤 필요', fitting: '공용 골격 연결', part_review: '갈아입기 검수' };
function row(index: number): WardrobeRow { return { key: crypto.randomUUID(), name: `상의 ${index}`, slot: 'top', garment_type: 'top', description: '' }; }
const draftKey = 'gaesup.wardrobe.batch.draft.v1';
function draft(): { name: string; rows: WardrobeRow[]; referenceCharacterId?: string } {
  try {
    const value = JSON.parse(sessionStorage.getItem(draftKey) || 'null');
    if (typeof value?.name === 'string' && Array.isArray(value.rows) && value.rows.length > 0 && value.rows.length <= 16 &&
      value.rows.every((r: WardrobeRow) => [r.key, r.name, r.slot, r.garment_type, r.description].every(v => typeof v === 'string'))) return { ...value, referenceCharacterId: typeof value.referenceCharacterId === 'string' ? value.referenceCharacterId : '' };
  } catch { /* Discard only an unreadable local draft, never an accepted request. */ }
  return { name: '교체 의상 일괄 생산', rows: [row(1), row(2)] };
}

export function WardrobeBatchPanel({ base, select, characters }: { base?: StandardItem; select: (id: string) => void; characters: Character[] }) {
  const [initial] = useState(draft);
  const [rows, setRows] = useState<WardrobeRow[]>(initial.rows);
  const [name, setName] = useState(initial.name), [items, setItems] = useState<Batch[]>([]);
  const [referenceCharacterId, setReferenceCharacterId] = useState(initial.referenceCharacterId || new URLSearchParams(location.search).get('character') || '');
  const references = characters.filter(c => c.artifacts.some(a => a.id === 'reference'));
  const referenceCharacter = references.find(c => c.id === referenceCharacterId);
  const reference = referenceCharacter?.artifacts.find(a => a.id === 'reference');
  const [error, setError] = useState(''), [connection, setConnection] = useState(''), [busy, setBusy] = useState(false);
  const active = useRef(false), submitting = useRef(false);
  useEffect(() => { sessionStorage.setItem(draftKey, JSON.stringify({ name, rows, referenceCharacterId })); }, [name, rows, referenceCharacterId]);
  async function refresh() { const value = await batchApi.list(); if (active.current) { setItems(value.items); setConnection(''); } }
  useEffect(() => {
    active.current = true; let loading = false;
    const reload = async () => { if (loading || document.hidden) return; loading = true; try { await refresh(); } catch (e) { if (active.current) setConnection((e as Error).message); } finally { loading = false; } };
    void reload(); const timer = setInterval(() => void reload(), 2500); window.addEventListener('online', reload);
    return () => { active.current = false; clearInterval(timer); window.removeEventListener('online', reload); };
  }, []);
  async function run(task: () => Promise<Batch>) {
    if (submitting.current) return; submitting.current = true; setBusy(true); setError('');
    try { await task(); await refresh(); } catch (e) { if (active.current) setError((e as Error).message); }
    finally { submitting.current = false; if (active.current) setBusy(false); }
  }
  function change(key: string, patch: Partial<WardrobeRow>) { setRows(rows.map(r => r.key === key ? { ...r, ...patch } : r)); }
  return <section className="wardrobe-batch" aria-label="의상 일괄 생산">
    <h2>같은 몸에 갈아입힐 의상 일괄 생산</h2>
    <p>선택한 캐릭터 원본과 고정 몸을 참고해 의상 시안을 받은 뒤, 그 이미지를 Meshy 3D 입력으로 사용합니다. 같은 슬롯에 여러 의상을 만들어 갈아입힐 수 있습니다.</p>
    {!base && <p>기준 몸의 붙어 있는 헤어·옷과 동작을 검수한 뒤 생산 기준 몸을 선택하세요.</p>}
    {(error || connection) && <p role="alert">{error || connection}</p>}
    {batchApi.pending() && <button disabled={busy} onClick={() => void run(() => batchApi.create())}>응답을 잃은 배치 복구</button>}
    <fieldset disabled={busy || batchApi.pending()}><legend>생산할 의상 목록</legend>
      <label>배치 이름<input value={name} onChange={e => setName(e.target.value)} maxLength={80} /></label>
      <label>참고할 캐릭터 원본<select aria-label="배치 참고 원본" value={referenceCharacterId} onChange={e => setReferenceCharacterId(e.target.value)}>
        <option value="">원본 이미지 선택</option>{references.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
      </select></label>
      {reference && <figure className="batch-reference"><img src={reference.url} alt={`${referenceCharacter!.name} 배치 참고 원본`} /><figcaption>{referenceCharacter!.name} → 의상 시안 → Meshy 3D</figcaption></figure>}
      {!references.length && <p>캐릭터 라이브러리에 원본 이미지를 등록하면 여기서 선택할 수 있습니다.</p>}
      {base && <p>{base.name} · {base.contract.height_m}m · {base.result?.bones.length}개 본 · 기준 {base.model_sha256?.slice(0, 12)}</p>}
      {rows.map((r, i) => <div className="batch-input-row" key={r.key}>
        <label>의상 {i+1} 이름<input aria-label={`의상 ${i+1} 이름`} value={r.name} onChange={e => change(r.key, { name: e.target.value })} maxLength={80} /></label>
        <label>교체 슬롯<select aria-label={`의상 ${i+1} 슬롯`} value={r.slot} onChange={e => change(r.key, { slot: e.target.value, garment_type: e.target.value === 'bottom' ? 'pants' : e.target.value.startsWith('shoe') ? 'shoe' : e.target.value })}>{Object.entries(slots).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
        {r.slot === 'bottom' && <label>형태<select value={r.garment_type} onChange={e => change(r.key, { garment_type: e.target.value })}><option value="pants">바지</option><option value="skirt">치마</option></select></label>}
        <label>모양·색·재질<textarea aria-label={`의상 ${i+1} 설명`} placeholder="예: 흰색 반팔 티셔츠, 둥근 목, 장식 없음" value={r.description} onChange={e => change(r.key, { description: e.target.value })} maxLength={3000} /></label>
        <button disabled={rows.length === 1} onClick={() => setRows(rows.filter(v => v.key !== r.key))}>의상 {i+1} 삭제</button>
      </div>)}
      <button disabled={rows.length >= 16} onClick={() => setRows([...rows, row(rows.length+1)])}>의상 추가</button>
      <p>총 {rows.length}개 · Sunburst 시안 최대 {rows.length}회 + Meshy 7 형상 최대 {rows.length}회 · 의상별 추가 리깅 0회</p>
      <p>일괄 생성 후 착용점을 정렬하고 같은 배치를 이어갑니다. 맞춤 검사를 통과한 파츠는 아래 조합에서 갈아입힐 수 있습니다.</p>
      <button disabled={!base || !reference || !name.trim() || rows.some(r => !r.name.trim() || r.description.trim().length < 5)} onClick={() => void run(async () => {
        const asset = await standardApi.captureReference(reference!.url);
        return batchApi.create({ name, base_id: base!.id, base_sha256: base!.model_sha256, reference_asset: asset.id, rows, max_images_per_row: 1, max_meshy_tasks_per_row: 1 });
      })}>의상 {rows.length}개 일괄 생산 시작</button>
    </fieldset>
    {items.map(batch => <article className="batch-status" key={batch.id} data-batch-id={batch.id}>
      <h3>{batch.name}</h3><p role="status">{batch.busy ? '배치 실행 중' : '항목별 상태 확인'} · 맞춤 완료 {batch.ready_count}/{batch.rows.length} · {batch.spec.height_m}m · {batch.spec.bones.length}개 본</p>
      <p>{batch.limits.image_model} / {batch.limits.shape_model} · 요청 상한 {batch.limits.images} + {batch.limits.meshy_generation}회</p>
      {batch.reference_image_url && <figure className="batch-reference"><img src={batch.reference_image_url} alt={`${batch.name} 고정 참고 원본`} /><figcaption>이 배치에 고정한 참고 이미지</figcaption></figure>}
      {batch.error && <p role="alert">{batch.error}</p>}
      <button disabled={busy || !batch.can_resume} onClick={() => void run(() => batchApi.resume(batch.id))}>배치 전체 이어가기</button>
      <div className="batch-results">{batch.rows.map(r => <section key={r.key}><strong>{r.name} · {slots[r.slot]}</strong><p>{stages[r.stage]}</p>
        {r.design?.artifacts.find(a => a.name === 'generated.png') && <img src={r.design.artifacts.find(a => a.name === 'generated.png')!.url} alt={`${r.name} 시안`} />}
        {r.error && <p role="alert">{r.error}</p>}
        {r.design && <button onClick={() => select(r.design!.id)}>시안 확인·정렬</button>}
        {r.shape && <button onClick={() => select(r.shape!.id)}>형상·기존 작업 확인</button>}
        {r.part && <button onClick={() => select(r.part!.id)}>맞춤·동작 확인</button>}
      </section>)}</div>
    </article>)}
  </section>;
}
