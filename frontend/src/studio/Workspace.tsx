import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react';
import { factoryApi, type FactoryJob } from '../factory/api';
import { usePolling } from '../use-polling';
import { studioApi } from './api';
import { NativeAssembly } from '../factory/NativeAssembly';
import { ProductionProgress } from '../factory/ProductionProgress';
import { StageRunner } from '../factory/StageRunner';
import { PartProgress } from '../factory/PartProgress';
import '../factory/character-factory.css';
import './workspace.css';

const MeshyMotion = lazy(() => import('../factory/MeshyMotion').then(m => ({ default: m.MeshyMotion })));
const BodyFactory = lazy(() => import('../factory/CharacterFactory').then(m => ({ default: m.CharacterFactory })));
const Animals = lazy(() => import('./Animals'));
const tabs = { admin: '관리자페이지', animals: '동물', character: '캐릭터', textures: '텍스쳐' };
const labels: Record<string, string> = { hair: '헤어', hat: '모자', top: '상의', bottom: '바지 · 치마', shoes: '신발', weapon: '무기', tool: '도구', glasses: '안경' };

export function Workspace() {
  const initial = new URLSearchParams(location.search);
  const [tab, setTab] = useState<keyof typeof tabs>((initial.get('tab') || '') in tabs ? initial.get('tab') as keyof typeof tabs : 'character');
  const [baseId, setBaseId] = useState(initial.get('base') || '');
  const [jobId, setJobId] = useState(initial.get('job') || '');
  const [creatingBody, setCreatingBody] = useState(false);
  const jobs = usePolling(factoryApi.list, 5000), catalog = usePolling(studioApi.catalog, 15000);
  const candidates = (jobs.value?.jobs || []).filter(j => j.production_mode === 'character_parts').sort((a,b) => b.created_at.localeCompare(a.created_at));
  const bases = candidates.filter(j => j.character_flow?.stage === 'complete' && !catalog.value?.items[j.id]?.archived);
  const base = (tab === 'admin' ? candidates : bases).find(j => j.id === baseId) || bases[0];
  const readNative = useCallback((signal: AbortSignal) => base ? factoryApi.nativeParts(base.id, signal) : Promise.resolve(null), [base?.id]);
  const native = usePolling(readNative, 10000);
  const job = candidates.find(j => j.id === jobId) || base;
  const [slots, setSlots] = useState(['top', 'bottom', 'shoes']);
  const [hairLength, setHairLength] = useState<'source' | 'short' | 'long'>('source');
  const [descriptions, setDescriptions] = useState<Record<string, string>>({});
  const [error, setError] = useState(''), [busy, setBusy] = useState(false);
  const locked = useRef(false);
  const pending = studioApi.pendingVariant();
  useEffect(() => {
    const query = new URLSearchParams(location.search);
    query.set('tab', tab);
    if (baseId) query.set('base', baseId);
    if (jobId) query.set('job', jobId);
    history.replaceState(null, '', `/?${query}`);
  }, [tab, baseId, jobId]);
  async function perform(action: () => Promise<void>) {
    if (locked.current) return;
    locked.current = true; setBusy(true); setError('');
    try { await action(); } catch (e) { setError((e as Error).message); }
    finally { locked.current = false; setBusy(false); }
  }
  const name = (j: FactoryJob) => catalog.value?.items[j.id]?.name || `${j.character_name} · ${new Date(j.created_at).toLocaleString()}`;
  const preview = (j: FactoryJob) => j.artifacts.find(a => a.name === 'body-front.png') || j.artifacts.find(a => a.name === 'body-image.png');
  return <div className="character-factory workspace">
    <header><strong>gaesup</strong><nav aria-label="제작 공간">{Object.entries(tabs).map(([key, label]) => <button key={key} aria-current={tab === key ? 'page' : undefined} onClick={() => setTab(key as keyof typeof tabs)}>{label}</button>)}</nav><span className={`connection-indicator ${jobs.error ? 'offline' : ''}`} aria-label={jobs.error ? '연결 끊김' : '연결됨'} /></header>
    {(error || jobs.error || catalog.error) && <p className="workspace-error" role="alert">{error || jobs.error || catalog.error}</p>}
    {tab === 'character' && <main>
      <section className="character-input"><h1>캐릭터</h1>
        <label>기본 몸<select value={base?.id || ''} disabled={busy || !!pending} onChange={e => { setBaseId(e.target.value); setJobId(''); }}><option value="" disabled>선택</option>{bases.map(j => <option key={j.id} value={j.id}>{name(j)}</option>)}</select></label>
        {native.value?.artifacts.find(a => a.name === 'body-front.png') && <img className="base-portrait" src={native.value.artifacts.find(a => a.name === 'body-front.png')!.url} alt="선택한 기본 몸" />}
        <fieldset disabled={busy || !!pending}><legend>생성할 파츠</legend>{Object.entries(labels).map(([slot, label]) => <label className="slot-choice" key={slot}><input type="checkbox" checked={slots.includes(slot)} onChange={e => setSlots(current => e.target.checked ? [...current, slot] : current.filter(s => s !== slot))} />{label}</label>)}</fieldset>
        {slots.includes('hair') && <label>헤어 길이<select value={hairLength} disabled={busy || !!pending} onChange={e => setHairLength(e.target.value as typeof hairLength)}><option value="source">원본 비율</option><option value="short">숏컷</option><option value="long">롱컷</option></select></label>}
        {slots.map(slot => <label key={slot}>{labels[slot]} 디자인<textarea maxLength={2000} disabled={busy || !!pending} value={descriptions[slot] || ''} onChange={e => setDescriptions(current => ({ ...current, [slot]: e.target.value }))} /></label>)}
        <button className="character-create" disabled={busy || (!pending && (!base || !native.value?.version || !slots.length))} onClick={() => void perform(async () => {
          if (!base || !native.value?.version) return;
          const result = await studioApi.variant(pending?.input || { base_job_id: base.id, base_version: native.value.version, slots, hair_length: hairLength, descriptions: Object.fromEntries(slots.map(s => [s, descriptions[s] || ''])) });
          setJobId(result.id); jobs.setValue(current => ({ jobs: [result, ...(current?.jobs || []).filter(j => j.id !== result.id)] }));
        })}>{busy ? '접수 중' : pending ? '요청 복구' : '파츠 생성'}</button>
        <small>유료 이미지 {(pending?.input.slots.length || slots.length)*2}장 · 3D {pending?.input.slots.length || slots.length}개</small>
        {job && <><label>결과 버전<select value={job.id} onChange={e => setJobId(e.target.value)}>{candidates.map(j => <option key={j.id} value={j.id}>{name(j)}</option>)}</select></label><PartProgress job={job} busy={busy} retryImage={(slot, view, failure_id) => perform(async () => { await factoryApi.retryImages(job.id, [{slot, view, failure_id}]); await jobs.refresh(); })} /></>}
      </section><section className="character-result">{job ? <><ProductionProgress job={job} offline={!!jobs.error} /><StageRunner jobId={job.id} key={`stage-${job.id}`} onChange={() => void jobs.refresh()} /><NativeAssembly key={job.id} jobId={job.id} simple flow={job.character_flow} /></> : <div className="character-empty">저장된 기본 몸 없음</div>}</section>
    </main>}
    {tab === 'admin' && <div className="workspace-content"><div className="workspace-heading"><h1>에셋 관리</h1><button onClick={() => setCreatingBody(!creatingBody)}>{creatingBody ? '목록' : '기본 몸 추가'}</button></div>
      {creatingBody ? <Suspense fallback={<p>불러오는 중</p>}><BodyFactory /></Suspense> : <>
        <div className="asset-grid">{candidates.map(j => <button className={`asset-card ${base?.id === j.id ? 'selected' : ''}`} key={j.id} onClick={() => setBaseId(j.id)}>{preview(j) && <img loading="lazy" src={preview(j)!.url} alt="기본 몸" />}<strong>{name(j)}</strong><small>{j.character_flow?.message || j.status}</small></button>)}</div>
        {base && <section className="management-panel"><h2>{name(base)}</h2><form key={base.id} onSubmit={e => { e.preventDefault(); const data = new FormData(e.currentTarget); void perform(async () => { catalog.setValue(await studioApi.saveMetadata(base.id, String(data.get('name')), data.get('archived') === 'on', catalog.value!.revision)); }); }}><label>이름<input name="name" required maxLength={80} defaultValue={catalog.value?.items[base.id]?.name || base.character_name} /></label><label className="slot-choice"><input type="checkbox" name="archived" defaultChecked={catalog.value?.items[base.id]?.archived || false} />보관</label><button disabled={busy || !catalog.value}>저장</button></form>
          <div className="artifact-grid">{native.value?.artifacts.filter(a => a.name.endsWith('.glb')).map(a => <a key={a.name} href={a.url} download>{a.name}</a>)}</div>
          <button disabled={busy || !native.value?.version || ['accepted', 'running'].includes(native.value.status) || !!base.character_flow?.busy} onClick={() => void perform(async () => { native.setValue(await factoryApi.assemble(base.id, true)); })}>기본 자세 정렬 · 새 버전 저장</button>
          <Suspense fallback={<p>동작 불러오는 중</p>}><MeshyMotion key={base.id} jobId={base.id} /></Suspense>
        </section>}</>}
    </div>}
    {tab === 'textures' && <Textures />}
    {tab === 'animals' && <Suspense fallback={<p>불러오는 중</p>}><Animals /></Suspense>}
  </div>;
}

function Textures() {
  const listing = usePolling(studioApi.textures, 15000);
  const [surface, setSurface] = useState('snow'), [size, setSize] = useState(512), [seed, setSeed] = useState(1);
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  const locked = useRef(false);
  const surfaces: Record<string, string> = { snow: '눈', sand: '모래', grass: '잔디', soil: '흙', stone: '돌' };
  return <div className="workspace-content"><h1>텍스쳐</h1><form className="texture-form" onSubmit={e => { e.preventDefault(); if (locked.current) return; locked.current = true; setBusy(true); setError(''); void studioApi.texture({surface, size, seed}).then(result => listing.setValue(current => ({items: [result, ...(current?.items || []).filter(t => t.id !== result.id)]}))).catch(e => setError(e.message)).finally(() => {locked.current = false; setBusy(false);}); }}>
    <label>타일<select value={surface} onChange={e => setSurface(e.target.value)}>{Object.entries(surfaces).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label><label>해상도<select value={size} onChange={e => setSize(Number(e.target.value))}>{[256, 512, 1024].map(n => <option key={n} value={n}>{n} × {n}</option>)}</select></label><label>시드<input type="number" min={0} max={2147483647} value={seed} onChange={e => setSeed(Number(e.target.value))} /></label><button disabled={busy}>{busy ? '생성 중' : '타일 생성'}</button></form>
    {(error || listing.error) && <p role="alert">{error || listing.error}</p>}<div className="asset-grid">{listing.value?.items.map(t => <article className="asset-card" key={t.id}><div className="tile-preview" style={{backgroundImage: `url(${t.artifacts.find(a => a.name === 'albedo.webp')?.url})`}} /><strong>{surfaces[t.surface]} · {t.size}px · {t.seed}</strong><small>GPU {(t.gpu.estimated_bytes_with_mips/1048576).toFixed(1)} MiB</small><div className="artifact-grid">{t.artifacts.map(a => <a key={a.name} href={a.url} download>{a.name}</a>)}</div></article>)}</div>
  </div>;
}
