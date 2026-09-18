import { useCallback, useEffect, useRef, useState } from 'react';
import { useAssetStore, type AssetRecord } from 'gaesup-world/assets';
import { api } from '../api';
import { avatarApi } from '../avatar/api';
import { AvatarViewport } from '../avatar/viewport';
import type { AvatarRuntime } from '../avatar/runtime/AvatarRuntime';
import type { AvatarState, EquipmentSlot } from '../avatar/core/types';
import { useLiveCharacters } from '../studio/characters';
import { StudioIcon } from '../studio/icons';
import { SourceEditor } from './SourceEditor';
import { factoryApi, type FactoryJob, type FaceSelection } from './api';
import './factory.css';
import { ImageWorkbench } from './ImageWorkbench';
import { StandardFactory } from './StandardFactory';
import { MeshyMotion } from './MeshyMotion';
import { NativeAssembly } from './NativeAssembly';

const names: Record<string, string> = { body: '공통 몸', face: '얼굴·머리', hair: '헤어', hat: '모자', top: '상의', bottom: '하의', onepiece: '원피스', shoes: '신발', back: '액세서리' };
const statusNames: Record<string, string> = { accepted: '생산 대기', running: '생산 중', review_required: '검수 대기', approved: '승인됨', failed: '생산 실패', recovery_required: '복구 필요' };
const stages = [['queued', '원본 접수'], ['body', '공통 몸 설계'], ['segment', '의상·파츠 분리'], ['fit', '몸에 맞추기'], ['rig', '동일 리깅'], ['verify', '출력·동작 검수']];
const reviewNames: Record<string,string> = {'body.png':'기본복 · 대머리 몸체', 'rest.png':'정면', 'side.png':'측면', 'pose.png':'변형 검사'};
const wholeStages = [['queued', '원본 접수'], ['images', '전신 시안'], ['meshy', '전신 3D 생성']];
const isWholeCharacter = (job?: FactoryJob) => job?.input_kind === 'image' && (job.production_mode === 'character_parts' || job.parts?.length === 1 && job.parts[0].slot === 'body');

function Result({ job, bodyOnly, assets }: { job: FactoryJob; bodyOnly: boolean; assets: AssetRecord[] }) {
  const wholeBody = isWholeCharacter(job);
  const [runtime, setRuntime] = useState<AvatarRuntime | null>(null), [error, setError] = useState('');
  const [backend, setBackend] = useState('초기화 중'), [pose, setPose] = useState('idle');
  const [state, setState] = useState<AvatarState>(job.outfit!);
  const [info, setInfo] = useState(''), [busy, setBusy] = useState(false);
  const compatible = assets.filter(asset => (asset.metadata?.['avatar'] as {rig?:string}|undefined)?.rig === (job.profile?.rig || 'gaesup-humanoid-v1'));
  const initial = useRef<AvatarState>(bodyOnly ? { body: job.outfit!.body, equipment: {} } : job.outfit!);
  const ready = useCallback((value: AvatarRuntime) => { setRuntime(value); setState(value.getState()); setInfo(`${value.getDiagnostics().boneCount}개 뼈 · 공통 스켈레톤`); }, []);
  const failed = useCallback((error: Error) => setError(error.message), []);
  async function equip(slot: EquipmentSlot, id: string) {
    if (!runtime || busy) return;
    setBusy(true); setError('');
    try { if (id) await runtime.equip(slot, id); else runtime.unequip(slot); setState(runtime.getState()); }
    catch (error) { setError((error as Error).message); } finally { setBusy(false); }
  }
  return <div className="factory-result" data-factory-ready={runtime ? job.id : ''}>
    <div className="factory-result-view"><AvatarViewport initial={initial.current} onReady={ready} onError={failed} onBackend={setBackend} /><span className="factory-renderer">{backend} · {info}</span></div>
    <div className="factory-motion">{['idle', 'walk', 'run', 'jump', 'sit', 'armsUp', 'crouch'].map(name => <button key={name} disabled={!runtime} aria-pressed={pose === name} onClick={() => { runtime?.playAnimation(name); setPose(name); }}>{name}</button>)}</div>
    {!bodyOnly && !wholeBody && <div className="factory-swaps"><strong>생산한 파츠 교체</strong>{Object.entries(names).filter(([slot]) => slot !== 'body' && compatible.some(asset => asset.metadata?.['factory'] && (asset.metadata?.['avatar'] as { slot: string }).slot === slot)).map(([slot, label]) => <label key={slot}>{label}<select aria-label={`생산 ${label} 교체`} disabled={!runtime || busy} value={state.equipment[slot as EquipmentSlot] || ''} onChange={event => void equip(slot as EquipmentSlot, event.target.value)}><option value="">장착 해제</option>{compatible.filter(asset => asset.metadata?.['factory'] && (asset.metadata?.['avatar'] as { slot: string }).slot === slot).map(asset => <option key={asset.id} value={asset.id}>{asset.name}</option>)}</select></label>)}</div>}
    {error && <p className="factory-error" role="alert">{error}</p>}
  </div>;
}

export function Factory() {
  if (new URLSearchParams(location.search).get('stage') === 'standard') return <StandardFactory />;
  return new URLSearchParams(location.search).get('stage') === 'glb' ? <GLBFactory /> : <ImageWorkbench />;
}

function GLBFactory() {
  const live = useLiveCharacters();
  const [sourceId, setSourceId] = useState(new URLSearchParams(location.search).get('character') || '');
  const [jobs, setJobs] = useState<FactoryJob[]>([]), [assets, setAssets] = useState<AssetRecord[]>([]);
  const [jobId, setJobId] = useState(new URLSearchParams(location.search).get('job')||''), [tab, setTab] = useState<'source' | 'body' | 'result'>(new URLSearchParams(location.search).get('tab')==='result'?'result':new URLSearchParams(location.search).get('tab')==='body'?'body':'source');
  const [error, setError] = useState(''), [connection, setConnection] = useState('');
  const [busy, setBusy] = useState(false), busyRef = useRef(false);
  const [checked, setChecked] = useState<string[]>([]), [selections, setSelections] = useState<FaceSelection[]>([]);
  const pending = factoryApi.pending();
  const source = live.characters.find(c => c.id === sourceId) || live.characters.find(c => c.model_id) || live.characters[0];
  const versions = jobs.filter(job => job.character_id === source?.id).sort((a, b) => b.created_at.localeCompare(a.created_at));
  const job = versions.find(value => value.id === jobId) || versions[0];
  const refresh = useCallback(async () => {
    try { const result = await factoryApi.list(); setJobs(result.jobs); setConnection(''); }
    catch (error) { setConnection((error as Error).message); }
  }, []);
  useEffect(() => {
    let active = true;
    const reload = () => { if (active && !document.hidden) void refresh(); };
    reload(); const timer = setInterval(reload, 2000); window.addEventListener('online', reload);
    return () => { active = false; clearInterval(timer); window.removeEventListener('online', reload); };
  }, [refresh]);
  const catalogRevision = jobs.filter(job => job.outfit).map(job => job.id).sort().join(',');
  useEffect(() => {
    let active = true;
    void avatarApi.catalog().then(records => { if (active) { useAssetStore.getState().registerAssets(records); setAssets(records); } }).catch(error => { if (active) setError(error.message); });
    return () => { active = false; };
  }, [catalogRevision]);
  function select(id: string) {
    setSourceId(id); setJobId(''); setTab('source'); setSelections([]);
    const url = new URL(location.href); url.searchParams.set('character', id); history.replaceState(null, '', url);
  }
  async function produce(ids: string[]) {
    if (busyRef.current) return;
    busyRef.current = true; setBusy(true); setError('');
    try {
      const recovery = factoryApi.pending();
      if (recovery) {
        const restored = await factoryApi.produce(recovery.input); setJobId(restored.id); setSourceId(restored.character_id);
      } else {
        for (const id of ids) {
          const character = live.characters.find(c => c.id === id);
          if (!character?.model_sha256) continue;
          const created = await factoryApi.produce({ character_id: id, source_sha256: character.model_sha256, selections: id === source?.id ? selections : [] });
          if (id === source?.id) setJobId(created.id);
        }
      }
      await refresh();
    } catch (error) { setError((error as Error).message); }
    finally { busyRef.current = false; setBusy(false); }
  }
  async function upload(file?: File) {
    if (!file || busyRef.current) return;
    busyRef.current = true; setBusy(true); setError('');
    try {
      if (!file.name.toLowerCase().endsWith('.glb')) throw new Error('Meshy 등에서 받은 GLB 파일을 선택하세요.');
      const record = await api.create(file.name.replace(/\.glb$/i, ''), null);
      await api.upload(record, file, 'model'); await live.refresh(); select(record.id);
    } catch (error) { setError((error as Error).message); }
    finally { busyRef.current = false; setBusy(false); }
  }
  const wholeBody = isWholeCharacter(job);
  const complete = wholeBody ? job.artifacts.some(a => a.name === 'generated-body.glb') : !!job?.outfit && assets.some(asset => asset.id === job.outfit!.body);
  const partSet = job?.production_mode === 'character_parts';
  const productionStages = partSet ? [['queued', '원본 접수'], ['images', '7개 파츠 시안'], ['models', '파츠별 3D 생성']] : wholeBody ? wholeStages : stages;
  const renderNames = wholeBody ? { ...reviewNames, 'body.png': '통짜 전신', 'body-image.png': '생성된 전신 시안' } : reviewNames;
  const designImage = job?.artifacts.find(a => a.name === 'body-image.png');
  const activeStage = ['review_required', 'approved'].includes(job?.status || '') ? productionStages.length : productionStages.findIndex(([id]) => id === job?.progress.stage);
  return <div className="factory-shell">
    <header className="factory-header"><a className="factory-brand" href="/avatar.html"><StudioIcon name="cube" size={25} /> gaesup <span>AVATAR FACTORY</span></a><nav><a href="/">캐릭터 라이브러리</a><a href="/avatar.html?view=wardrobe">런타임 옷장</a></nav><span className={`factory-connection ${connection || live.failure ? 'offline' : ''}`}>{connection || live.failure ? '재연결 대기' : '로컬 공장 연결됨'}</span></header>
    <aside className="factory-sidebar"><span className="factory-eyebrow">SOURCE CHARACTERS</span><h2>캐릭터 투입</h2><p>Meshy·Tripo·Blender에서 받은 캐릭터를 같은 규격의 아바타로 만듭니다.</p>
      <label className="factory-upload">＋ GLB 가져오기<input aria-label="공장 GLB 가져오기" type="file" accept=".glb" disabled={busy} onChange={event => { void upload(event.target.files?.[0]); event.target.value = ''; }} /></label>
      <div className="factory-sources">{live.characters.map(c => {
        const thumbnail = c.artifacts.find(a => a.id === 'rest_render') || c.artifacts.find(a => a.id === 'reference');
        return <div className={`factory-source-row ${source?.id === c.id ? 'selected' : ''}`} key={c.id}><input aria-label={`${c.name} 일괄 생산 선택`} type="checkbox" disabled={!c.model_id} checked={checked.includes(c.id)} onChange={event => setChecked(ids => event.target.checked ? [...ids, c.id] : ids.filter(id => id !== c.id))} /><button onClick={() => select(c.id)}>{thumbnail ? <img src={thumbnail.url} alt="" /> : <StudioIcon name="cube" />}<span><strong>{c.name}</strong><small>{c.model_id ? `${c.parts.length}개 원본 파츠 · GLB 있음` : '이미지만 있음 · GLB 필요'}</small></span></button></div>;
      })}</div>
      <button className="factory-batch" disabled={!checked.length || busy || !!pending} onClick={() => void produce(checked)}>선택한 {checked.length}개 일괄 생산</button><p className="factory-small">공통 규격으로 순차 생산합니다. 원본과 이전 생산 버전은 보존됩니다.</p>
      <div className="factory-profile"><span className="factory-eyebrow">{wholeBody ? 'WHOLE CHARACTER' : 'COMMON BODY STANDARD'}</span><h3>{job?.profile?.name || 'Maple SD'}</h3>{!wholeBody && <svg viewBox="0 0 200 220" aria-label="공통 몸 비율 설계도"><g fill="#c9dcc0" stroke="#d5f4ae" strokeWidth="1.3"><ellipse cx="100" cy="51" rx="41" ry="44" /><path d="M85 93 Q100 88 115 93 L122 133 Q100 146 78 133Z" /><ellipse cx="71" cy="119" rx="10" ry="25" transform="rotate(29 71 119)" /><ellipse cx="129" cy="119" rx="10" ry="25" transform="rotate(-29 129 119)" /><rect x="80" y="136" width="17" height="54" rx="8"/><rect x="103" y="136" width="17" height="54" rx="8"/></g><g stroke="#809671" strokeDasharray="3 3"><path d="M25 8H175M25 96H175M25 194H175M158 8V194"/></g><g fill="#9cab91" fontSize="9"><text x="165" y="60">HEAD</text><text x="165" y="152">BODY</text></g></svg>}<dl><div><dt>비율</dt><dd>{wholeBody ? '생성 원본 유지' : `${job?.profile?.head_ratio || 2.45}등신`}</dd></div><div><dt>{wholeBody ? '리깅 경로' : '공통 리그'}</dt><dd>{wholeBody ? 'Meshy 원본 골격' : '23 bones · A-pose'}</dd></div><div><dt>몸</dt><dd>{wholeBody ? '머리 포함 전신' : '새 공통 템플릿'}</dd></div></dl></div>
    </aside>
    <main className="factory-main"><div className="factory-heading"><div><span className="factory-eyebrow">{partSet ? 'PARTS → ONE MOVING CHARACTER' : wholeBody ? 'CHARACTER → WHOLE AVATAR' : 'CHARACTER → MODULAR AVATAR'}</span><h1>{source?.name || '아바타 공장'}</h1><p>{partSet ? '몸·헤어·모자·의상·신발을 조합하고, 같은 골격으로 함께 움직입니다.' : wholeBody ? '머리부터 발끝까지, 반팔·반바지를 입은 통짜 전신 모델.' : '기본 몸 설계부터 의상 분리, 공통 리깅, 교체 가능한 파츠 출력까지.'}</p></div>{wholeBody ? <a className="factory-primary" href={`/avatar.html?character=${encodeURIComponent(source?.id || '')}`}>{partSet ? '전체 파츠 분리 화면' : '전신 제작 화면'}</a> : <button className="factory-primary" disabled={busy || (!source?.model_id && !pending) || (!pending && ['accepted', 'running'].includes(job?.status || ''))} onClick={() => void produce(source ? [source.id] : [])}>{busy ? '접수 중…' : pending ? '생산 요청 복구' : job ? '새 버전 생산' : '모듈형 아바타 생산'}</button>}</div>
      <ol className="factory-stages" style={wholeBody ? {gridTemplateColumns: 'repeat(3, 1fr)'} : undefined}>{productionStages.map(([id, label], index) => <li key={id} className={index < activeStage ? 'done' : index === activeStage ? 'active' : ''}><span>{index < activeStage ? '✓' : String(index+1).padStart(2, '0')}</span><strong>{label}</strong></li>)}</ol>
      {(error || connection || live.failure) && <div className="factory-error" role="alert">{error || connection || live.failure}<button onClick={() => { void refresh(); void live.refresh(); }}>다시 연결</button></div>}
      {job && <div className="factory-job-status"><span className={`factory-job-dot ${job.status}`} /><strong>{statusNames[job.status] || job.status}</strong><span>{job.status === 'review_required' ? (partSet ? '파츠별 3D 생성 결과입니다. 기본몸 리깅과 파츠 맞춤은 별도로 확인하세요.' : wholeBody ? '전신 생성 완료. Meshy 리깅과 동작을 아래에서 확인하세요.' : '공통 몸·파츠 출력 완료. 외형과 변형을 확인하세요.') : job.error || job.progress.message}</span><select aria-label="생산 버전" value={job.id} onChange={event => { setJobId(event.target.value); setTab('source'); }}>{versions.map(v => <option key={v.id} value={v.id}>{new Date(v.created_at).toLocaleString()} · {statusNames[v.status] || v.status}</option>)}</select></div>}
      <section className="factory-workspace"><div className="factory-tabs"><button aria-pressed={tab === 'source'} onClick={() => setTab('source')}>{wholeBody ? '전신 시안' : '원본 · 분리 영역'}</button>{!wholeBody && <button aria-pressed={tab === 'body'} disabled={!complete} onClick={() => setTab('body')}>공통 기본 몸</button>}<button aria-pressed={tab === 'result'} disabled={!complete} onClick={() => setTab('result')}>{partSet ? '파츠 조합 · 전체 동작' : wholeBody ? '전신 결과 · 동작 확인' : '생산 결과 · 파츠 교체'}</button>{!wholeBody && <span>{selections.reduce((n, s) => n+s.faces.length, 0)}개 보정 면</span>}</div>
        {source && tab === 'source' && (wholeBody ? (designImage ? <img src={designImage.url} alt="생성된 전신 시안" style={{ display: 'block', maxWidth: '100%', maxHeight: 640, margin: 'auto' }} /> : <div className="factory-empty">전신 시안을 생성하고 있습니다.</div>) : <SourceEditor key={source.id} character={source} onSelections={setSelections} />)}
        {complete && tab !== 'source' && (partSet ? <NativeAssembly key={job.id} jobId={job.id} /> : wholeBody ? <MeshyMotion key={job.id} jobId={job.id} /> : <Result key={`${job.id}:${tab}`} job={job} assets={assets} bodyOnly={tab === 'body'} />)}
        {!source && <div className="factory-empty">캐릭터 GLB를 가져오면 생산을 시작할 수 있습니다.</div>}
      </section>
      {job?.technical && !wholeBody && <section className="factory-output"><div><span className="factory-eyebrow">PRODUCTION PACKAGE</span><h2>{wholeBody ? '머리 포함 통짜 전신 모델' : '같은 몸, 같은 리그, 교체 가능한 파츠'}</h2><p>{job.technical.bone_count}개 {wholeBody ? '로컬 뼈 · 통짜 전신 1개' : `공통 뼈 · ${job.technical.parts}개 파츠`} · 원본 보존 · 외형 검수 대기</p>{job.technical.file_bytes!==undefined&&<p>조립 파일 {(job.technical.file_bytes/1024/1024).toFixed(2)} MiB · 텍스처 {((job.technical.texture_pixels||0)/1e6).toFixed(1)} MP · 원본 해상도 유지{job.technical.resource_warnings?.length?' · 권장 용량 초과는 안내로만 표시합니다.':''}</p>}</div><div className="factory-downloads">{job.artifacts.filter(a => ['master.blend', 'character.glb', 'body.glb', 'generated-body.glb', 'compilation.json'].includes(a.name)).map(a => <a key={a.name} href={a.url} download><StudioIcon name="download" size={16} />{a.name}</a>)}</div><div className="factory-renders">{job.artifacts.filter(a => a.name in renderNames).map(a => <a key={a.name} href={a.url} target="_blank" rel="noreferrer"><img src={a.url} alt={renderNames[a.name]} /><span>{renderNames[a.name]}</span></a>)}</div><div className="factory-limitations">{job.evidence?.limitations.map(value => <p key={value}>{value}</p>)}</div></section>}
    </main>
  </div>;
}
