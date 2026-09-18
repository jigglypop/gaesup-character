import { useEffect, useRef, useState } from 'react';
import { api, request } from '../api';
import { useLiveCharacters } from '../use-live-characters';
import { usePolling } from '../use-polling';
import { factoryApi, type FactoryJob, type ImageRetry } from './api';
import type { Blueprint } from './image-layers';
import { NativeAssembly } from './NativeAssembly';
import { ProductionProgress } from './ProductionProgress';
import { StageRunner } from './StageRunner';
import { PartProgress } from './PartProgress';
import './character-factory.css';

const partSlots = ['body', 'hair', 'hat', 'top', 'bottom', 'shoes'];

export function CharacterFactory() {
  const live = useLiveCharacters();
  const [characterId, setCharacterId] = useState(new URLSearchParams(location.search).get('character') || '');
  const [jobId, setJobId] = useState(new URLSearchParams(location.search).get('job') || '');
  const listing = usePolling(factoryApi.list);
  const configuration = usePolling(factoryApi.capabilities, 5000);
  const jobs = listing.value?.jobs || [], capabilities = configuration.value;
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  const [hairLength, setHairLength] = useState<'source' | 'short' | 'long'>('source');
  const locked = useRef(false), alive = useRef(true);
  const partJobs = jobs.filter(j => j.production_mode === 'character_parts').sort((a, b) => b.created_at.localeCompare(a.created_at));
  const suggested = partJobs.find(j => j.id === jobId) || partJobs[0];
  const source = characterId ? live.characters.find(c => c.id === characterId) : live.characters.find(c => c.id === suggested?.character_id) || live.characters.find(c => c.artifacts.some(a => a.id === 'reference'));
  const versions = partJobs.filter(j => j.character_id === source?.id);
  const job = jobId ? versions.find(j => j.id === jobId) : versions[0];
  const reference = source?.artifacts.find(a => a.id === 'reference');
  const running = job?.character_flow?.busy ?? (!!job && ['pipeline_queued', 'pipeline_running', 'accepted', 'running'].includes(job.status));
  const connectionError = listing.error || configuration.error || live.failure;
  const pending = source ? factoryApi.pendingImage(source.id) : null;
  const compatible = capabilities?.character_pipeline === 'parts_to_character_v2'
    && partSlots.every(slot => capabilities.slots?.includes(slot));
  const canGenerate = compatible && capabilities?.next_actions.some(a => a.id === 'produce_images' && a.enabled);
  const retryBatch = job?.next_actions?.find(a => a.id === 'retry_images' && a.enabled)?.images;

  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  function remember(character: string, job = '') {
    setCharacterId(character); setJobId(job);
    const q = new URLSearchParams({ character }); if (job) q.set('job', job);
    history.replaceState(null, '', `/?${q}`);
  }
  async function upload(file?: File) {
    if (!file || locked.current) return;
    locked.current = true; setBusy(true); setError('');
    try {
      const character = await api.create(file.name.replace(/\.[^.]+$/, ''), null);
      await api.upload(character, file, 'image');
      if (!alive.current) return;
      remember(character.id); await live.refresh();
    } catch (e) { if (alive.current) setError((e as Error).message); }
    finally { locked.current = false; if (alive.current) setBusy(false); }
  }
  async function produce() {
    if (!source || locked.current) return;
    locked.current = true; setBusy(true); setError('');
    try {
      let result: FactoryJob;
      if (pending) result = await factoryApi.produceImage(pending.input);
      else {
        const blueprint = await request<Blueprint>(`/api/avatar-blueprints/${source.id}`);
        if (!blueprint.source_sha256) throw new Error('캐릭터 사진을 먼저 올려 주세요.');
        result = await factoryApi.produceImage({ character_id: source.id, source_sha256: blueprint.source_sha256,
          blueprint_revision: blueprint.revision, production_mode: 'character_parts', view_mode: 'front_side', image_mode: 'generate',
          slots: partSlots, hair_length: hairLength, body_purpose: 'wardrobe_base', rig_with_meshy: true, motion_actions: {} });
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
  return <div className="character-factory">
    <header><strong>gaesup</strong><span className={`connection-indicator ${connectionError ? 'offline' : ''}`} title={listing.receivedAt ? new Date(listing.receivedAt).toLocaleTimeString() : undefined} aria-label={connectionError ? '연결 끊김' : '연결됨'} /></header>
    <main>
      <section className="character-input">
        <h1>캐릭터 제작</h1>
        <label className="character-upload">{reference ? <img src={reference.url} alt="캐릭터 원본 사진" /> : <span>캐릭터 사진을 올려 주세요</span>}<b>{reference ? '사진 바꾸기' : '사진 선택'}</b><input aria-label="캐릭터 사진" type="file" accept="image/png,image/jpeg" disabled={busy} onChange={e => { void upload(e.target.files?.[0]); e.target.value = ''; }} /></label>
        {live.characters.length > 0 && <details className="character-history"><summary>작업 선택</summary><select aria-label="작업 선택" disabled={busy} value={source?.id || ''} onChange={e => remember(e.target.value)}><option value="" disabled>선택</option>{live.characters.filter(c => c.artifacts.some(a => a.id === 'reference') || partJobs.some(j => j.character_id === c.id)).map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></details>}
        <label className="character-history">머리카락 길이<select aria-label="머리카락 길이" disabled={busy || running || !!pending} value={pending ? pending.input.hair_length || 'source' : hairLength} onChange={e => setHairLength(e.target.value as typeof hairLength)}><option value="source">원본대로</option><option value="short">숏컷</option><option value="long">롱컷</option></select></label>
        <button className="character-create" disabled={busy || (!pending && (running || !reference || !compatible || !canGenerate))} onClick={() => void produce()}>{busy ? '접수 중' : pending ? '요청 복구' : running ? '생성 중' : '생성'}</button>
        <details className="character-generation"><summary>유료 생성 범위</summary><small>이미지 {(pending?.input.slots.length || partSlots.length) * (pending && pending.input.view_mode !== 'front_side' ? 1 : 2)}장 · 3D {pending?.input.slots.length || partSlots.length}개 · 리깅 1회</small></details>
        {(error || connectionError) && <p role="alert">{error || connectionError}</p>}
        {!canGenerate && capabilities && <p className="character-status" role="status">{compatible ? '생성 서비스 연결 대기' : '서버 업데이트 대기'}</p>}
        {jobId && !job && !listing.loading && !connectionError && <p role="alert">선택한 작업을 찾을 수 없습니다. 제작 버전을 다시 선택해 주세요.</p>}
        {versions.length > 1 && <label className="character-history">제작 버전<select aria-label="제작 버전" value={job?.id || ''} onChange={e => remember(source!.id, e.target.value)}><option value="" disabled>버전 선택</option>{versions.map(v => <option key={v.id} value={v.id}>{new Date(v.created_at).toLocaleString()}</option>)}</select></label>}
        {retryBatch && <button disabled={busy || running} onClick={() => void retryImages(retryBatch)}>실패한 이미지 병렬 재요청 · 유료 {retryBatch.length}장</button>}
        {job && <PartProgress job={job} busy={busy} retryImage={(slot, view, failure_id) => retryImages([{slot, view, failure_id}])} />}
      </section>
      <section className="character-result" aria-label="완성 캐릭터">
        {job && <ProductionProgress job={job} offline={!!connectionError} />}
        {job && <StageRunner key={job.id} jobId={job.id} onChange={() => { void listing.refresh(); }} />}
        {job ? <NativeAssembly key={job.id} jobId={job.id} simple flow={job.character_flow} /> : <div className="character-empty"><h2>캐릭터 미리보기</h2><p>{listing.loading ? '작업 불러오는 중…' : '제작 결과 없음'}</p></div>}
      </section>
    </main>
  </div>;
}
