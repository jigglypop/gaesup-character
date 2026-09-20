import { useCallback, useEffect, useRef, useState, type ClipboardEvent as ReactClipboardEvent, type DragEvent as ReactDragEvent } from 'react';
import { api, request } from '../api';
import { useLiveCharacters } from '../use-live-characters';
import { usePolling } from '../use-polling';
import { factoryApi, type FactoryJob, type ImageRetry } from './api';
import type { Blueprint } from './image-layers';
import { NativeAssembly } from './NativeAssembly';
import { ProductionProgress } from './ProductionProgress';
import { StageRunner } from './StageRunner';
import { PartProgress } from './PartProgress';
import { RigRecovery } from './RigRecovery';
import { isCatalogJobDeleted, studioApi } from '../studio/api';
import './character-factory.css';
import { MeshyOptionsEditor } from '../studio/MeshyOptionsEditor';
import { useMeshyOptions, meshyOptionsError } from '../studio/meshy-options';

const partSlots = ['body', 'hair', 'hat', 'top', 'bottom', 'shoes'] as const;

type CharacterFactoryProps = { embedded?: boolean };

function clipboardImage(data: DataTransfer | null) {
  if (!data) return undefined;
  return [...data.files].find(isSupportedImage);
}

function hasDraggedFiles(data: DataTransfer) {
  return [...data.types].includes('Files');
}

function isSupportedImage(file: File) {
  return file.type === 'image/png' || file.type === 'image/jpeg';
}

export function CharacterFactory({ embedded = false }: CharacterFactoryProps) {
  const characterQuery = embedded ? 'photoCharacter' : 'character';
  const jobQuery = embedded ? 'photoJob' : 'job';
  const live = useLiveCharacters();
  const [characterId, setCharacterId] = useState(new URLSearchParams(location.search).get(characterQuery) || '');
  const [jobId, setJobId] = useState(new URLSearchParams(location.search).get(jobQuery) || '');
  const listing = usePolling(factoryApi.list, 15000);
  const readSelected = useCallback((signal: AbortSignal) => jobId ? factoryApi.detail(jobId, signal) : Promise.resolve(null), [jobId]);
  const selectedJob = usePolling(readSelected, 5000);
  const configuration = usePolling(factoryApi.capabilities, 5000);
  const currentJob = selectedJob.value?.id === jobId ? selectedJob.value : null;
  const jobs = currentJob ? [currentJob, ...(listing.value?.jobs || []).filter(item => item.id !== currentJob.id)] : listing.value?.jobs || [];
  const capabilities = configuration.value;
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  const meshy = useMeshyOptions('photo-parts');
  const [meshyUploading, setMeshyUploading] = useState(false);
  const [draggingPhoto, setDraggingPhoto] = useState(false);
  const [hairLength, setHairLength] = useState<'source' | 'short' | 'long'>('source');
  const [baseId, setBaseId] = useState(new URLSearchParams(location.search).get('photoBase') || '');
  const [useCommonBody, setUseCommonBody] = useState(!new URLSearchParams(location.search).has('photoBase') && new URLSearchParams(location.search).get('photoBody') !== 'new');
  const catalog = usePolling(studioApi.catalog, 15000);
  const bodyProfile = usePolling(factoryApi.bodyProfile, 15000);
  const locked = useRef(false), alive = useRef(true), fileInput = useRef<HTMLInputElement>(null), dragDepth = useRef(0);
  const partJobs = jobs.filter(j => j.production_mode === 'character_parts').sort((a, b) => b.created_at.localeCompare(a.created_at));
  const suggested = partJobs.find(j => j.id === jobId) || partJobs[0];
  const source = characterId ? live.characters.find(c => c.id === characterId) : live.characters.find(c => c.id === suggested?.character_id) || live.characters.find(c => c.artifacts.some(a => a.id === 'reference'));
  const versions = partJobs.filter(j => j.character_id === (source?.id || characterId || suggested?.character_id));
  const job = jobId ? versions.find(j => j.id === jobId) : versions[0];
  const reference = source?.artifacts.find(a => a.id === 'reference');
  const running = job?.character_flow?.busy ?? (!!job && ['pipeline_queued', 'pipeline_running', 'accepted', 'running'].includes(job.status));
  const connectionError = listing.error || configuration.error || live.failure;
  const pending = source ? factoryApi.pendingImage(source.id) : null;
  const selectedBaseId = pending ? pending.input.base_job_id || '' : baseId || (useCommonBody ? bodyProfile.value?.body?.job_id || '' : '');
  const bases = partJobs.filter(item => !item.base_job_id && ['complete', 'expressions'].includes(item.character_flow?.stage || '')
    && !isCatalogJobDeleted(item, catalog.value) && !catalog.value?.items[item.id]?.archived && !catalog.value?.parts?.[`${item.id}:body`]?.deleted);
  const readBase = useCallback(async (signal: AbortSignal) => selectedBaseId
    ? { id: selectedBaseId, native: await factoryApi.nativeParts(selectedBaseId, signal) } : null, [selectedBaseId]);
  const baseState = usePolling(readBase, 10000);
  const selectedBase = baseState.value?.id === selectedBaseId ? baseState.value.native : undefined;
  const selectedBaseVersion = pending?.input.base_version || (useCommonBody && selectedBaseId === bodyProfile.value?.body?.job_id
    ? bodyProfile.value.body.version : selectedBase?.version);
  const baseReady = !selectedBaseId || (bases.some(item => item.id === selectedBaseId)
    && selectedBase?.status === 'review_required' && !!selectedBaseVersion
    && selectedBase.artifacts.some(item => item.name === 'body.glb'));
  const generationSlots = selectedBaseId ? partSlots.filter(slot => slot !== 'body') : partSlots;
  const compatible = capabilities?.character_pipeline === 'parts_to_character_v2'
    && partSlots.every(slot => capabilities.slots?.includes(slot));
  const canGenerate = compatible && capabilities?.next_actions.some(a => a.id === 'produce_images' && a.enabled);
  const retryBatch = job?.next_actions?.find(a => a.id === 'retry_images' && a.enabled)?.images;
  const normalizedReference = job?.artifacts.find(a => a.name === job.reference_preparation?.file);
  const normalizedSideReference = job?.artifacts.find(a => a.name === job.reference_preparation?.views?.side?.file);
  const normalizesReference = pending ? !!pending.input.prepare_reference : true;
  const generatesExpressions = pending ? !!pending.input.default_expressions : true;
  const modelCount = pending ? pending.input.slots.length - (selectedBaseId ? 1 : 0) : generationSlots.length;
  const partViewCount = pending
    ? pending.input.view_mode === 'single' ? 1 : pending.input.view_mode === 'front_side_back' ? 3 : 2
    : 3;
  const partImageCount = modelCount * partViewCount;
  const totalImageCount = partImageCount + (normalizesReference ? 2 : 0) + (generatesExpressions ? 5 : 0);

  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  useEffect(() => {
    const query = new URLSearchParams(location.search);
    if (baseId) { query.set('photoBase', baseId); query.delete('photoBody'); }
    else { query.delete('photoBase'); if (useCommonBody) query.delete('photoBody'); else query.set('photoBody', 'new'); }
    history.replaceState(null, '', `${location.pathname}?${query}${location.hash}`);
  }, [baseId, useCommonBody]);
  function remember(character: string, job = '') {
    setCharacterId(character); setJobId(job);
    const q = new URLSearchParams(location.search);
    if (character) q.set(characterQuery, character); else q.delete(characterQuery);
    if (job) q.set(jobQuery, job); else q.delete(jobQuery);
    history.replaceState(null, '', `${location.pathname}?${q}${location.hash}`);
  }
  async function upload(file?: File) {
    if (!file || locked.current) return;
    if (!isSupportedImage(file)) { setError('PNG 또는 JPEG 사진을 선택해 주세요.'); return; }
    locked.current = true; setBusy(true); setError('');
    try {
      const character = await api.create(file.name.replace(/\.[^.]+$/, ''), null);
      await api.upload(character, file, 'image');
      if (!alive.current) return;
      remember(character.id); await live.refresh();
    } catch (e) { if (alive.current) setError((e as Error).message); }
    finally { locked.current = false; if (alive.current) setBusy(false); }
  }
  const uploadCurrent = useRef(upload);
  uploadCurrent.current = upload;
  useEffect(() => {
    const paste = (event: ClipboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target?.closest('input, textarea, [contenteditable="true"]')) return;
      const file = clipboardImage(event.clipboardData);
      if (!file) return;
      event.preventDefault();
      void uploadCurrent.current(file);
    };
    window.addEventListener('paste', paste);
    return () => window.removeEventListener('paste', paste);
  }, []);
  useEffect(() => {
    const preventFileNavigation = (event: DragEvent) => {
      if (!event.dataTransfer || !hasDraggedFiles(event.dataTransfer)) return;
      event.preventDefault();
      if (event.type === 'drop') {
        dragDepth.current = 0;
        setDraggingPhoto(false);
      }
    };
    window.addEventListener('dragover', preventFileNavigation);
    window.addEventListener('drop', preventFileNavigation);
    return () => {
      window.removeEventListener('dragover', preventFileNavigation);
      window.removeEventListener('drop', preventFileNavigation);
    };
  }, []);
  function pasteUpload(event: ReactClipboardEvent<HTMLElement>) {
    const file = clipboardImage(event.clipboardData);
    if (!file) return;
    event.preventDefault();
    event.stopPropagation();
    void upload(file);
  }
  function enterPhotoDrop(event: ReactDragEvent<HTMLElement>) {
    if (!hasDraggedFiles(event.dataTransfer)) return;
    event.preventDefault();
    event.stopPropagation();
    if (locked.current) return;
    dragDepth.current += 1;
    setDraggingPhoto(true);
  }
  function leavePhotoDrop(event: ReactDragEvent<HTMLElement>) {
    if (!hasDraggedFiles(event.dataTransfer)) return;
    event.preventDefault();
    event.stopPropagation();
    dragDepth.current = Math.max(0, dragDepth.current - 1);
    if (dragDepth.current === 0) setDraggingPhoto(false);
  }
  function overPhotoDrop(event: ReactDragEvent<HTMLElement>) {
    if (!hasDraggedFiles(event.dataTransfer)) return;
    event.preventDefault();
    event.stopPropagation();
    event.dataTransfer.dropEffect = locked.current ? 'none' : 'copy';
  }
  function dropPhoto(event: ReactDragEvent<HTMLElement>) {
    if (!hasDraggedFiles(event.dataTransfer)) return;
    event.preventDefault();
    event.stopPropagation();
    dragDepth.current = 0;
    setDraggingPhoto(false);
    if (locked.current) return;
    const files = [...event.dataTransfer.files];
    if (files.length !== 1 || !isSupportedImage(files[0])) {
      setError('PNG 또는 JPEG 사진 1개만 놓아 주세요.');
      return;
    }
    void upload(files[0]);
  }
  async function produce() {
    if (!source || locked.current || (!pending && !baseReady)) return;
    locked.current = true; setBusy(true); setError('');
    try {
      let result: FactoryJob;
      if (pending) result = await factoryApi.produceImage(pending.input);
      else {
        if (meshyOptionsError(meshy.options)) throw new Error(meshyOptionsError(meshy.options));
        const blueprint = await request<Blueprint>(`/api/avatar-blueprints/${source.id}`);
        if (!blueprint.source_sha256) throw new Error('캐릭터 사진을 먼저 올려 주세요.');
        result = await factoryApi.produceImage({ character_id: source.id, source_sha256: blueprint.source_sha256,
          blueprint_revision: blueprint.revision, production_mode: 'character_parts', view_mode: 'front_side_back', image_mode: 'generate',
          prepare_reference: true, default_expressions: true, meshy_options: meshy.options,
          ...(selectedBaseId && selectedBaseVersion ? { base_job_id: selectedBaseId, base_version: selectedBaseVersion } : {}),
          slots: [...partSlots], hair_length: hairLength, body_purpose: 'wardrobe_base', rig_with_meshy: true });
      }
      if (alive.current) { listing.setValue(current => ({ jobs: [result, ...(current?.jobs || []).filter(j => j.id !== result.id)] })); remember(result.character_id, result.id); }
    } catch (e) { if (alive.current) setError((e as Error).message); }
    finally { locked.current = false; if (alive.current) setBusy(false); }
  }
  async function retryImages(images: ImageRetry[]) {
    if (!job || locked.current) return;
    locked.current = true; setBusy(true); setError('');
    try {
      const result = await factoryApi.retryImages(job.id, images);
      if (alive.current) listing.setValue(current => ({ jobs: [result, ...(current?.jobs || []).filter(j => j.id !== result.id)] }));
    } catch (e) { if (alive.current) setError((e as Error).message); }
    finally { locked.current = false; if (alive.current) setBusy(false); }
  }
  return <div className={`character-factory ${embedded ? 'character-factory-embedded' : ''}`}>
    {!embedded && <header><strong>GAESUP-STORE</strong><span className={`connection-indicator ${connectionError ? 'offline' : ''}`} title={listing.receivedAt ? new Date(listing.receivedAt).toLocaleTimeString() : undefined} aria-label={connectionError ? '연결 끊김' : '연결됨'} /></header>}
    <main>
      <section className="character-input">
        <h1>사진으로 전체 생성</h1>
        <label className={`character-upload ${draggingPhoto ? 'is-dragging' : ''}`} tabIndex={busy ? -1 : 0} role="button" aria-disabled={busy} onPaste={pasteUpload} onDragEnter={enterPhotoDrop} onDragLeave={leavePhotoDrop} onDragOver={overPhotoDrop} onDrop={dropPhoto} onKeyDown={event => { if (!busy && (event.key === 'Enter' || event.key === ' ')) { event.preventDefault(); fileInput.current?.click(); } }}>{reference ? <img src={reference.url} alt="캐릭터 원본 사진" /> : <span>캐릭터 사진을 클릭하거나 놓거나 Ctrl+V로 붙여넣으세요</span>}<b>{reference ? '사진 바꾸기 · 끌어놓기 가능' : '사진 선택 · 끌어놓기 가능'}</b><input ref={fileInput} aria-label="캐릭터 사진" type="file" accept="image/png,image/jpeg" disabled={busy} onChange={e => { void upload(e.target.files?.[0]); e.target.value = ''; }} /></label>
        {live.characters.length > 0 && <details className="character-history"><summary>작업 선택</summary><select aria-label="작업 선택" disabled={busy} value={source?.id || ''} onChange={e => remember(e.target.value)}><option value="" disabled>선택</option>{live.characters.filter(c => c.artifacts.some(a => a.id === 'reference') || partJobs.some(j => j.character_id === c.id)).map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></details>}
        <label className="character-history">기본 몸<select aria-label="기본 몸" value={selectedBaseId} disabled={busy || running || !!pending} onChange={event => { setBaseId(event.target.value); setUseCommonBody(false); }}>
          <option value="">사진에서 새 기본 몸 생성</option>
          {selectedBaseId && !bases.some(item => item.id === selectedBaseId) && <option value={selectedBaseId}>선택한 기본 몸 · {selectedBaseId}</option>}
          {bases.map(item => <option key={item.id} value={item.id}>{item.id === bodyProfile.value?.body?.job_id ? '공통 기본 몸 · ' : ''}{catalog.value?.parts?.[`${item.id}:body`]?.name || catalog.value?.items[item.id]?.name || item.character_name} · {new Date(item.created_at).toLocaleString()}</option>)}
        </select></label>
        {selectedBaseId && <div className="character-base-preview">
          {selectedBase?.artifacts.find(item => item.name === 'body-front.png') && <img className="base-portrait" src={selectedBase.artifacts.find(item => item.name === 'body-front.png')!.url} alt="선택한 기본 몸만 미리보기" />}
          <small>기본 몸·골격·저장된 동작 재사용 · 새 사진의 파츠 맞춤</small>
          {!baseReady && <p role="status">{baseState.error || '사용할 수 있는 기본 몸을 확인 중입니다.'}</p>}
        </div>}
        <label className="character-history">머리카락 길이<select aria-label="머리카락 길이" disabled={busy || running || !!pending} value={pending ? pending.input.hair_length || 'source' : hairLength} onChange={e => setHairLength(e.target.value as typeof hairLength)}><option value="source">원본대로</option><option value="short">숏컷</option><option value="long">롱컷</option></select></label>
        <a className="prompt-management-link" href="/?tab=prompts&promptGroup=parts" target="_blank" rel="noreferrer">프롬프트 관리 열기</a>
        <MeshyOptionsEditor value={pending?.input.meshy_options || meshy.options} disabled={busy || running || !!pending} onChange={meshy.setOptions} onUploading={setMeshyUploading} />
        {meshy.storageError && <p role="alert">{meshy.storageError}</p>}
        <button className="character-create" disabled={busy || meshyUploading || (!pending && (running || !reference || !compatible || !canGenerate || !baseReady))} onClick={() => void produce()}>{busy ? '접수 중' : pending ? '요청 복구' : running ? '생성 중' : selectedBaseId ? '선택한 몸에 사진 파츠 생성' : '사진으로 전체 생성'}</button>
        <details className="character-generation"><summary>생성 작업 범위</summary><small>유료 이미지 총 {totalImageCount}장 · {normalizesReference && '규격 2장 + '}파츠 {partImageCount}장{generatesExpressions && ' + 기본 표정 5장'} · 3D {modelCount}개 · {selectedBaseId ? '기존 몸·리깅·동작 재사용' : '리깅 1회 · 기본 동작 5종'}</small></details>
        {(error || connectionError || catalog.error || bodyProfile.error || baseState.error) && <p role="alert">{error || connectionError || catalog.error || bodyProfile.error || baseState.error}</p>}
        {!canGenerate && capabilities && <p className="character-status" role="status">{compatible ? '생성 서비스 연결 대기' : '서버 업데이트 대기'}</p>}
        {jobId && !job && !listing.loading && !connectionError && <p role="alert">선택한 작업을 찾을 수 없습니다. 제작 버전을 다시 선택해 주세요.</p>}
        {versions.length > 1 && <label className="character-history">제작 버전<select aria-label="제작 버전" value={job?.id || ''} onChange={e => remember(source!.id, e.target.value)}><option value="" disabled>버전 선택</option>{versions.map(v => <option key={v.id} value={v.id}>{new Date(v.created_at).toLocaleString()}</option>)}</select></label>}
        {retryBatch && <button disabled={busy || running} onClick={() => void retryImages(retryBatch)}>실패한 이미지 병렬 재요청 · 유료 {retryBatch.length}장</button>}
        {job && <PartProgress job={job} busy={busy} retryImage={(slot, view, failure_id) => retryImages([{slot, view, failure_id}])} />}
      </section>
      <section className="character-result" aria-label="완성 캐릭터">
        {job && <ProductionProgress job={job} offline={!!connectionError} />}
        {job?.reference_preparation && <section className="character-reference" aria-label="공통 규격 이미지">
          <h3>공통 규격 · 배경 제거</h3>
          {normalizedReference ? <a href={normalizedReference.url} target="_blank" rel="noreferrer"><img src={normalizedReference.url} alt="공통 규격으로 맞추고 배경을 제거한 캐릭터" /></a>
            : <p role="status">{job.reference_preparation.failure?.message || job.error || (job.reference_preparation.status === 'pending' ? '대기 중' : '규격 이미지 준비 중')}</p>}
          {normalizedSideReference && <a href={normalizedSideReference.url} target="_blank" rel="noreferrer"><img src={normalizedSideReference.url} alt={'\uACF5\uD1B5 \uADDC\uACA9\uC73C\uB85C \uB9DE\uCD94\uACE0 \uBC30\uACBD\uC744 \uC81C\uAC70\uD55C \uC624\uB978\uCABD \uCE21\uBA74 \uCE90\uB9AD\uD130'} /></a>}
        </section>}
        {job && <RigRecovery jobId={job.id} onComplete={() => { void listing.refresh(); }} />}
        {job && <StageRunner key={`stages:${job.id}`} jobId={job.id} onChange={() => { void listing.refresh(); }} />}
        {job ? <NativeAssembly key={`assembly:${job.id}`} jobId={job.id} simple flow={job.character_flow} /> : <div className="character-empty"><h2>캐릭터 미리보기</h2><p>{listing.loading ? '작업 불러오는 중…' : '제작 결과 없음'}</p></div>}
      </section>
    </main>
  </div>;
}
