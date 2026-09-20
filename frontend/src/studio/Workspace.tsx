import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react';
import { factoryApi, type FactoryJob } from '../factory/api';
import { usePolling } from '../use-polling';
import { isCatalogJobDeleted, studioApi } from './api';
import { AssetGallery } from './AssetGallery';
import { partLabels as labels, variantSlots } from '../factory/parts';
import { SinglePart } from './SinglePart';
import '../factory/character-factory.css';
import './workspace.css';

const MeshyMotion = lazy(() => import('../factory/MeshyMotion').then(m => ({ default: m.MeshyMotion })));
const PhotoFactory = lazy(() => import('../factory/CharacterFactory').then(m => ({ default: m.CharacterFactory })));
const BaseBodies = lazy(() => import('./BaseBodies'));
const NativeAssembly = lazy(() => import('../factory/NativeAssembly').then(m => ({ default: m.NativeAssembly })));
const Animals = lazy(() => import('./Animals'));
const Textures = lazy(() => import('./Textures'));
const Generations = lazy(() => import('./Generations'));
const Emoticons = lazy(() => import('./Emoticons'));
const Prompts = lazy(() => import('./Prompts'));
const tabs = { admin: '관리자페이지', animals: '동물', character: '캐릭터', props: '기물', textures: '기본 바닥 타일', emoticons: '2D 이모티콘', prompts: '프롬프트 관리' };

export function Workspace() {
  const initial = new URLSearchParams(location.search);
  const [tab, setTab] = useState<keyof typeof tabs>((initial.get('tab') || '') in tabs ? initial.get('tab') as keyof typeof tabs : 'character');
  const [characterMode, setCharacterMode] = useState<'body' | 'photo' | 'parts'>(initial.get('mode') === 'photo' ? 'photo' : initial.get('mode') === 'parts' ? 'parts' : 'body');
  const [partType, setPartType] = useState<(typeof variantSlots)[number]>(variantSlots.find(slot => slot === initial.get('part')) || 'top');
  const [baseId, setBaseId] = useState(initial.get('base') || '');
  const [jobId, setJobId] = useState(initial.get('partsJob') || '');
  const [adminAssetId, setAdminAssetId] = useState(initial.get('asset') || '');
  const [composeId, setComposeId] = useState('');
  const [textureMode, setTextureMode] = useState<'basic' | 'prompt'>('basic');
  const jobs = usePolling(factoryApi.list, 5000), catalog = usePolling(studioApi.catalog, 15000), bodyProfile = usePolling(factoryApi.bodyProfile, 15000);
  const candidates = (jobs.value?.jobs || []).filter(j => j.production_mode === 'character_parts').sort((a,b) => b.created_at.localeCompare(a.created_at));
  const baseCandidates = candidates.filter(j => !j.base_job_id);
  const composeJob = candidates.find(j => j.id === composeId && !isCatalogJobDeleted(j, catalog.value));
  const bases = candidates.filter(j => ['complete', 'expressions'].includes(j.character_flow?.stage || '') && !isCatalogJobDeleted(j, catalog.value) && !catalog.value?.items[j.id]?.archived && !catalog.value?.parts?.[`${j.id}:body`]?.deleted);
  const basePool = tab === 'admin' ? baseCandidates : bases;
  const base = basePool.find(j => j.id === baseId) || (tab === 'admin' ? baseCandidates[0] : bases[0]);
  const baseVariants = base ? candidates.filter(j => j.base_job_id === base.id) : [];
  const managedAsset = [base, ...baseVariants].find(j => j?.id === adminAssetId) || base;
  const readNative = useCallback(async (signal: AbortSignal) => (tab === 'admin' || tab === 'character') && base ? { jobId: base.id, parts: await factoryApi.nativeParts(base.id, signal) } : null, [base?.id, tab]);
  const native = usePolling(readNative, 10000);
  const nativeState = native.value?.jobId === base?.id ? native.value?.parts : undefined;
  const readManagedNative = useCallback(async (signal: AbortSignal) => tab === 'admin' && managedAsset && managedAsset.id !== base?.id ? { jobId: managedAsset.id, parts: await factoryApi.nativeParts(managedAsset.id, signal) } : null, [base?.id, managedAsset?.id, tab]);
  const managedNative = usePolling(readManagedNative, 10000);
  const managedNativeState = managedAsset?.id === base?.id ? nativeState : managedNative.value?.jobId === managedAsset?.id ? managedNative.value.parts : undefined;
  const versions = base ? [base, ...baseVariants.filter(item => !catalog.value?.items[item.id]?.archived)] : [];
  const job = versions.find(j => j.id === jobId) || base;
  const [error, setError] = useState(''), [busy, setBusy] = useState(false);
  const locked = useRef(false);
  useEffect(() => {
    const query = new URLSearchParams(location.search);
    query.set('tab', tab);
    if (tab === 'character') query.set('mode', characterMode);
    if (tab === 'character' && characterMode === 'parts') query.set('part', partType);
    if (baseId) query.set('base', baseId); else query.delete('base');
    if (jobId) query.set('partsJob', jobId); else query.delete('partsJob');
    if (tab === 'admin' && adminAssetId) query.set('asset', adminAssetId); else query.delete('asset');
    history.replaceState(null, '', `/?${query}`);
  }, [tab, characterMode, partType, baseId, jobId, adminAssetId]);
  const receiveJob = useCallback((result: FactoryJob) => {
    setJobId(result.id);
    jobs.setValue(current => ({ jobs: [result, ...(current?.jobs || []).filter(item => item.id !== result.id)] }));
  }, [jobs.setValue]);
  function choosePart(slot: (typeof variantSlots)[number]) {
    setCharacterMode('parts'); setPartType(slot);
  }
  async function perform(action: () => Promise<void>) {
    if (locked.current) return;
    locked.current = true; setBusy(true); setError('');
    try { await action(); } catch (e) { setError((e as Error).message); }
    finally { locked.current = false; setBusy(false); }
  }
  const name = (j: FactoryJob) => catalog.value?.parts?.[`${j.id}:body`]?.name || catalog.value?.items[j.id]?.name || `${j.character_name} · ${new Date(j.created_at).toLocaleString()}`;
  const runtime = nativeState?.parts.reduce((total, part) => ({
    source: total.source + (part.runtime_budget?.source_triangles || 0),
    optimized: total.optimized + (part.runtime_budget?.runtime_triangles || 0),
    target: total.target + (part.runtime_budget?.target_triangles || 0),
    textures: total.textures + (part.runtime_budget?.resized_textures || 0),
  }), { source: 0, optimized: 0, target: 0, textures: 0 });
  const managedGlbs = [...(managedAsset?.artifacts || []), ...(managedNativeState?.artifacts || [])]
    .filter(artifact => artifact.name.endsWith('.glb'))
    .filter((artifact, index, items) => items.findIndex(item => item.name === artifact.name && item.url === artifact.url) === index);
  return <div className="character-factory workspace">
    <header><strong>GAESUP-STORE</strong><nav aria-label="제작 공간">{Object.entries(tabs).map(([key, label]) => <button key={key} aria-current={tab === key ? 'page' : undefined} onClick={() => setTab(key as keyof typeof tabs)}>{label}</button>)}</nav><span className={`connection-indicator ${jobs.error ? 'offline' : ''}`} aria-label={jobs.error ? '연결 끊김' : '연결됨'} /></header>
    {(error || jobs.error || catalog.error || bodyProfile.error || native.error || managedNative.error) && <p className="workspace-error" role="alert">{error || jobs.error || catalog.error || bodyProfile.error || native.error || managedNative.error}</p>}
    {tab === 'character' && <><nav className="character-workflow-switch character-part-tabs" aria-label="캐릭터 파츠 타입"><button aria-current={characterMode === 'body' ? 'page' : undefined} aria-pressed={characterMode === 'body'} onClick={() => setCharacterMode('body')}>기본몸</button>{(['top', 'bottom', 'hair', 'hat', 'shoes', 'weapon', 'tool', 'glasses'] as const).map(slot => <button key={slot} aria-current={characterMode === 'parts' && partType === slot ? 'page' : undefined} aria-pressed={characterMode === 'parts' && partType === slot} onClick={() => choosePart(slot)}>{slot === 'hat' ? '모자·장식' : labels[slot]}</button>)}<button aria-pressed={characterMode === 'photo'} onClick={() => setCharacterMode('photo')}>사진으로 전체 생성</button></nav>
    {characterMode === 'body' ? <Suspense fallback={<p className="workspace-content">불러오는 중</p>}><BaseBodies jobs={candidates.filter(item => !isCatalogJobDeleted(item, catalog.value))} onJob={receiveJob} refreshJobs={jobs.refresh} /></Suspense> : characterMode === 'photo' ? <Suspense fallback={<p className="workspace-content">불러오는 중</p>}><PhotoFactory embedded /></Suspense> : <SinglePart slot={partType} onSlotChange={choosePart} bases={bases} base={base} native={nativeState} versions={versions} job={job} name={name} onBaseChange={id => { setBaseId(id); setJobId(''); }} onJobChange={setJobId} onJob={receiveJob} refreshJobs={jobs.refresh} />}</>}
    {tab === 'admin' && <div className="workspace-content"><div className="workspace-heading"><h1>에셋 관리</h1><button onClick={() => { setTab('character'); setCharacterMode('body'); }}>기본몸 추가</button></div>
        <AssetGallery jobs={candidates} catalog={catalog.value} onCatalogChange={catalog.setValue} onRefresh={catalog.refresh} nativeJobId={managedAsset?.id} nativeState={managedNativeState} onOpen={item => { setBaseId(item.base_job_id || item.id); setAdminAssetId(item.id); setJobId(item.id); requestAnimationFrame(() => requestAnimationFrame(() => document.getElementById('admin-selection')?.scrollIntoView({ behavior: 'smooth', block: 'start' }))); }} onCompose={item => { setComposeId(item.id); requestAnimationFrame(() => requestAnimationFrame(() => document.getElementById('admin-composer')?.scrollIntoView({ behavior: 'smooth', block: 'start' }))); }} />
        {composeJob && <section className="management-panel asset-composer" id="admin-composer"><div className="workspace-heading"><h2>조합·표정 · {name(composeJob)}</h2><button onClick={() => setComposeId('')}>닫기</button></div><Suspense fallback={<p>조합 불러오는 중</p>}><NativeAssembly key={composeJob.id} jobId={composeJob.id} simple flow={composeJob.character_flow} /></Suspense></section>}
        <div className="admin-body-choice"><label>관리할 기본 몸<select value={base?.id || ''} onChange={e => { setBaseId(e.target.value); setAdminAssetId(e.target.value); setJobId(''); }}><option value="" disabled>선택</option>{baseCandidates.map(j => <option key={j.id} value={j.id}>{name(j)}{j.id === bodyProfile.value?.body?.job_id ? ' · 공통' : ''}</option>)}</select></label><button disabled={busy || !base || !nativeState?.version || !bodyProfile.value || (bodyProfile.value.body?.job_id === base.id && bodyProfile.value.body.version === nativeState.version)} onClick={() => void perform(async () => { bodyProfile.setValue(await factoryApi.saveBodyProfile(base!.id, nativeState!.version!, bodyProfile.value!.revision)); })}>{bodyProfile.value?.body?.job_id === base?.id ? '공통 기본 몸' : '공통 기본 몸으로 지정'}</button></div>
        {base && <><section className="management-panel" id="admin-selection"><h2>에셋</h2><div className="asset-version-list"><button className={managedAsset?.id === base.id ? 'selected' : ''} onClick={() => setAdminAssetId(base.id)}><strong>{name(base)}</strong><small>기본 몸</small></button>{baseVariants.map(item => <button className={managedAsset?.id === item.id ? 'selected' : ''} key={item.id} onClick={() => setAdminAssetId(item.id)}><strong>{name(item)}</strong><small>{item.requested_slots?.map(slot => labels[slot] || slot).join(', ') || '파츠'}</small></button>)}</div>
          {managedAsset && <form key={`${managedAsset.id}:${catalog.value?.revision}`} onSubmit={e => { e.preventDefault(); const data = new FormData(e.currentTarget); void perform(async () => { catalog.setValue(await studioApi.saveMetadata(managedAsset.id, String(data.get('name')), data.get('archived') === 'on', catalog.value!.revision)); }); }}><label>이름<input name="name" required maxLength={80} defaultValue={catalog.value?.items[managedAsset.id]?.name || managedAsset.character_name} /></label><label className="slot-choice"><input type="checkbox" name="archived" defaultChecked={catalog.value?.items[managedAsset.id]?.archived || false} />보관</label><button disabled={busy || !catalog.value}>저장</button></form>}
          <div className="artifact-grid">{managedGlbs.map(a => <a key={`${a.name}:${a.url}`} href={a.url} download>{a.name}</a>)}</div>
        </section><section className="management-panel base-motion-panel"><h2>기본 몸 동작 · {name(base)}</h2>
          {runtime && runtime.optimized > 0 && <dl className="runtime-budget"><div><dt>런타임 삼각형</dt><dd>{runtime.optimized.toLocaleString()}</dd></div><div><dt>원본 삼각형</dt><dd>{runtime.source.toLocaleString()}</dd></div><div><dt>파츠 예산 합계</dt><dd>{runtime.target.toLocaleString()}</dd></div><div><dt>축소 텍스쳐</dt><dd>{runtime.textures.toLocaleString()}</dd></div></dl>}
          <button disabled={busy || !nativeState?.version || ['accepted', 'running'].includes(nativeState.status) || !!base.character_flow?.busy} onClick={() => void perform(async () => { native.setValue({ jobId: base.id, parts: await factoryApi.assemble(base.id, true) }); })}>기본 자세 정렬 · 새 버전 저장</button>
          <Suspense fallback={<p>동작 불러오는 중</p>}><MeshyMotion key={base.id} jobId={base.id} visibleSlots={['idle', 'walk', 'run', 'jump', 'fall']} onRigRecovery={() => void native.refresh()} /></Suspense>
        </section></>}
    </div>}
    {tab === 'textures' && <><div className="character-workflow-switch" role="group" aria-label="텍스쳐 제작 방식"><button aria-pressed={textureMode === 'basic'} onClick={() => setTextureMode('basic')}>기본 타일</button><button aria-pressed={textureMode === 'prompt'} onClick={() => setTextureMode('prompt')}>프롬프트로 재질 생성</button></div><Suspense fallback={<p className="workspace-content">불러오는 중</p>}>{textureMode === 'basic' ? <Textures /> : <Generations key="texture" kind="texture" />}</Suspense></>}
    {tab === 'props' && <Suspense fallback={<p className="workspace-content">불러오는 중</p>}><Generations key="prop" kind="prop" /></Suspense>}
    {tab === 'emoticons' && <Suspense fallback={<p className="workspace-content">불러오는 중</p>}><Emoticons /></Suspense>}
    {tab === 'animals' && <Suspense fallback={<p>불러오는 중</p>}><Animals /></Suspense>}
    {tab === 'prompts' && <Suspense fallback={<p className="workspace-content">프롬프트 불러오는 중</p>}><Prompts /></Suspense>}
  </div>;
}
