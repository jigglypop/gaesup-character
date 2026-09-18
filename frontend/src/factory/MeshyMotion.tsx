import { useEffect, useRef, useState } from 'react';
import { ModelViewer } from '../viewer';
import { factoryApi, type MeshyAction, type MeshyState } from './api';
import './meshy-motion.css';
import { standardApi } from './standard-api';

const slots: Record<string, string> = { idle: '대기', walk: '걷기', run: '달리기', jump: '점프', fall: '낙하', sit: '앉기', armsUp: '팔 들기', crouch: '웅크리기' };

export function MeshyMotion({ jobId }: { jobId: string }) {
  const [state, setState] = useState<MeshyState>(), [library, setLibrary] = useState<MeshyAction[]>([]);
  const [defaults, setDefaults] = useState<Record<string, number>>({}), [slot, setSlot] = useState('walk');
  const [actionId, setActionId] = useState<number>(), [search, setSearch] = useState(''), [category, setCategory] = useState('');
  const [error, setError] = useState(''), [catalogError, setCatalogError] = useState(''), [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false), busyRef = useRef(false);
  const [clips, setClips] = useState<{name: string; index: number}[]>([]), [motion, setMotion] = useState(-1);
  const [ready, setReady] = useState(false), [previewError, setPreviewError] = useState('');
  const [recoveryId, setRecoveryId] = useState('');
  const mount = useRef<HTMLDivElement>(null), viewer = useRef<ModelViewer | null>(null);
  const chosen = library.find(a => a.action_id === actionId);
  const url = state?.artifacts.find(a => a.name === 'model.glb')?.url;
  const filtered = library.filter(a => (!category || a.category === category) && (!search || `${a.name} ${a.key} ${a.action_id}`.toLowerCase().includes(search.toLowerCase())));

  useEffect(() => {
    let alive = true;
    const refresh = () => void factoryApi.meshy(jobId).then(value => { if (alive) { setState(value); setError(''); } }).catch(e => { if (alive) setError(e.message); });
    refresh(); const timer = setInterval(refresh, 2500); window.addEventListener('online', refresh);
    return () => { alive = false; clearInterval(timer); window.removeEventListener('online', refresh); };
  }, [jobId]);
  async function loadLibrary() {
    try {
      const [catalog, saved] = await Promise.all([factoryApi.motionLibrary(), factoryApi.motionDefaults(jobId)]);
      setLibrary(catalog.items); setDefaults(saved.selections); setActionId(saved.selections[slot]); setCatalogError('');
    } catch (e) { setCatalogError((e as Error).message); }
  }
  useEffect(() => { void loadLibrary(); }, []);
  useEffect(() => {
    setReady(false); setClips([]); setMotion(-1); setPreviewError('');
    if (!url) return;
    let alive = true;
    const instance = new ModelViewer(mount.current!, 'studio'); viewer.current = instance;
    void instance.load(url).then(value => { if (alive) { setClips(value); setReady(true); } }).catch(e => { if (alive) setPreviewError(e.message); });
    return () => { alive = false; instance.dispose(); viewer.current = null; };
  }, [url]);

  async function perform(operation: () => Promise<unknown>, message: string) {
    if (busyRef.current) return;
    busyRef.current = true; setBusy(true); setNotice('');
    try { await operation(); setState(await factoryApi.meshy(jobId)); setNotice(message); }
    catch (e) { setNotice((e as Error).message); }
    finally { busyRef.current = false; setBusy(false); }
  }
  const running = busy || state?.busy;
  const pending = state?.actions.find(a => a.action_id === actionId);
  return <section className="meshy-motion" data-meshy-job={jobId} data-meshy-ready={ready ? state?.version : ''}>
    <header><h2>Meshy 리깅 · 실제 동작</h2><p>{state?.rig_task_id ? `Meshy 작업 ${state.rig_task_id}` : '생성된 전신 모델에 Meshy 리깅을 연결합니다.'}</p>
      <p>{state?.bone_count ? `Meshy 원본 골격 ${state.bone_count}개 본 · 원본 가중치 유지` : state?.busy ? `Meshy 처리 중 · ${state.progress}%` : 'Meshy 리깅 결과 대기'}</p>
      {!url && <button disabled={running || !state?.can_resume && state?.status !== 'not_started'} onClick={() => void perform(() => factoryApi.meshyRig(jobId), 'Meshy 작업을 접수했습니다.')}>{state?.status === 'not_started' ? 'Meshy 리깅 가져오기 · 유료 최대 1회' : '기존 Meshy 작업 조회·이어가기'}</button>}
      {url && state?.error && state.can_resume && <button disabled={running} onClick={() => void perform(() => factoryApi.meshyRig(jobId), '기존 작업을 조회합니다.')}>기존 작업 이어가기</button>}
      {(error || state?.error) && <p role="alert">{error || state?.error}</p>}
    </header>
    <div className="meshy-scene" ref={mount} />
    {previewError && <p role="alert">{previewError}</p>}
    {ready && <div className="meshy-clips"><button aria-pressed={motion === -1} onClick={() => { viewer.current?.play(-1); setMotion(-1); }}>기본 자세</button>{clips.map(c => <button key={c.index} aria-pressed={motion === c.index} onClick={() => { viewer.current?.play(c.index); setMotion(c.index); }}>{c.name}</button>)}</div>}
    {state?.clips.map(c => <p className="meshy-provenance" key={c.slot}>{slots[c.slot] || c.slot}: {c.source === 'rigging_basic' ? 'Meshy 리깅에 포함된 기본 동작' : `Meshy 선택 동작 #${c.action_id}`}</p>)}
    {state?.artifacts.map(a => <a className="meshy-download" key={a.name} href={a.url} download>{a.name === 'model.glb' ? 'Meshy 골격·동작 통합 GLB' : `Meshy 원본 ${a.name}`}</a>)}
    {state?.version && state.model_sha256 && <button disabled={running} onClick={() => void perform(async () => {
      const base = await standardApi.create('bases', { factory_job_id: jobId, factory_version: state.version,
        source_sha256: state.model_sha256, name: 'Meshy 전신 의상 규격 후보', height_m: 1.2 });
      location.href = `/avatar.html?stage=standard&item=${base.id}`;
    }, '의상 생산 기준 버전을 준비합니다.')}>이 몸·골격으로 의상 일괄 생산 준비</button>}
    {(state?.status === 'submission_uncertain' || state?.actions.some(a => a.status === 'submission_uncertain')) && <form onSubmit={e => {e.preventDefault(); void perform(() => factoryApi.meshyRecover(jobId, recoveryId, state.actions.find(a => a.status === 'submission_uncertain')?.action_id), '작업 ID를 복구했습니다. 기존 작업 이어가기를 누르세요.');}}><label>Meshy에서 확인한 기존 작업 ID<input aria-label="Meshy 기존 작업 ID" value={recoveryId} onChange={e => setRecoveryId(e.target.value)} required pattern="[a-zA-Z0-9_-]+" /></label><button disabled={running}>기존 작업 ID 복구</button></form>}
    <fieldset disabled={busy} className="meshy-picker"><legend>Meshy 동작을 하나씩 기본값으로 지정</legend>
      <p>공식 목록 {library.length}개 · 기본값 저장은 생성 요청을 보내지 않습니다. 선택한 동작만 이 캐릭터로 가져올 수 있습니다.</p>
      {catalogError && <p role="alert">{catalogError}<button onClick={() => void loadLibrary()}>동작 목록 다시 연결</button></p>}
      <div className="meshy-filters"><label>동작 슬롯<select aria-label="기본 동작 슬롯" value={slot} onChange={e => { setSlot(e.target.value); setActionId(defaults[e.target.value]); setNotice(''); }}>{Object.entries(slots).map(([key, name]) => <option key={key} value={key}>{name} ({key})</option>)}</select></label>
        <label>검색<input aria-label="Meshy 동작 검색" value={search} onChange={e => setSearch(e.target.value)} placeholder="이름 또는 action ID" /></label>
        <label>분류<select aria-label="Meshy 동작 분류" value={category} onChange={e => setCategory(e.target.value)}><option value="">전체</option>{Array.from(new Set(library.map(a => a.category))).map(value => <option key={value}>{value}</option>)}</select></label>
      </div>
      <div className="meshy-options"><label>실제 Meshy 동작<select size={8} aria-label="Meshy 동작 목록" value={actionId ?? ''} onChange={e => setActionId(Number(e.target.value))}>{!chosen && <option value="" disabled>동작을 선택하세요</option>}{chosen && !filtered.includes(chosen) && <option value={chosen.action_id}>{chosen.name} · #{chosen.action_id}</option>}{filtered.map(a => <option key={a.action_id} value={a.action_id}>{a.name} · #{a.action_id}</option>)}</select></label>
        <div className="meshy-action-preview">{chosen ? <><strong>{chosen.name} · #{chosen.action_id}</strong>{chosen.preview_url && <img src={chosen.preview_url} alt={`${chosen.name} Meshy 동작 미리보기`} />}<small>{chosen.category} / {chosen.sub_category}</small></> : <p>목록에서 고르면 Meshy 미리보기가 표시됩니다.</p>}</div>
      </div>
      <div className="meshy-buttons"><button disabled={!chosen} onClick={() => void perform(async () => { const saved = await factoryApi.saveMotionDefaults({...defaults, [slot]: actionId!}, jobId); setDefaults(saved.selections); }, `${slots[slot]} 기본 동작을 저장했습니다.`)}>이 동작을 {slots[slot]} 기본값으로 저장</button>
        <button disabled={!chosen || !url || running} onClick={() => void perform(() => factoryApi.meshyAction(jobId, slot, actionId!), '선택한 Meshy 동작을 가져오고 있습니다.')}>{pending ? '이 동작 조회·적용' : '이 캐릭터에 동작 가져오기 · 유료 최대 1회'}</button></div>
      {pending && <p>선택 동작 상태: {pending.status || '대기'}{pending.task_id ? ` · ${pending.task_id}` : ''}</p>}
      <p>저장한 기본값: {Object.entries(defaults).map(([key, id]) => `${slots[key]}: ${library.find(a => a.action_id === id)?.name || '#'+id}`).join(' / ') || '아직 지정하지 않음'}</p>
      {notice && <p role="status">{notice}</p>}
    </fieldset>
  </section>;
}
