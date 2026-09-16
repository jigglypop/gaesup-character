import { useEffect, useRef, useState } from 'react';
import { api } from '../api';
import { useLiveCharacters } from '../studio/characters';
import { ModelViewer } from '../viewer';
import { standardApi, type StandardItem } from './standard-api';
import './standard.css';
import { GenerateDesign, AlignDesign } from './StandardDesign';
import { WardrobeBatchPanel } from './WardrobeBatch';
import { StandardWardrobe } from './StandardWardrobe';

const statuses: Record<string, string> = { accepted: '실행 대기', running: 'Blender 작업 중', review_required: '검수 필요', approved: '기준 몸 고정됨', failed: '작업 실패', prepared: '시안 저장됨', provider_running: 'Meshy 생성 중', provider_paused: 'Meshy 조회·복구 필요', model_ready: '파츠 형상 준비됨', image_running: 'Sunburst 시안 생성 중', image_paused: '시안 응답 확인 필요', design_review_required: '시안 착용점 검수·정렬 필요' };
const kinds: Record<string, string> = { base: '기준 몸', part: '파츠', assembly: '조합', image: '파츠 시안', shape: 'Meshy 파츠 형상', design: '생성 시안' };

function Preview({ item }: { item: StandardItem }) {
  const mount = useRef<HTMLDivElement>(null), viewer = useRef<ModelViewer | null>(null);
  const [clips, setClips] = useState<{ index: number; name: string }[]>([]), [error, setError] = useState('');
  const [motion, setMotion] = useState(-1);
  const [ready, setReady] = useState(false);
  const url = item.artifacts.find(a => a.name === 'model.glb' || a.name === 'generated.glb')?.url;
  useEffect(() => {
    setClips([]); setError(''); setMotion(-1); setReady(false);
    if (!url) return;
    let alive = true; const instance = new ModelViewer(mount.current!, 'studio'); viewer.current = instance;
    void instance.load(url).then(value => { if (alive) { setClips(value); setReady(true); } }).catch(e => { if (alive) setError(e.message); });
    return () => { alive = false; instance.dispose(); viewer.current = null; };
  }, [url]);
  return <section className="standard-preview" data-standard-preview={item.id} data-standard-ready={ready ? item.id : ''}>
    <div className="standard-scene" ref={mount} />
    {url && !ready && !error && <p role="status">3D 모델을 불러오는 중…</p>}
    {url && <label>동작 검수<select aria-label="공용 골격 동작" value={motion} onChange={e => { setMotion(Number(e.target.value)); viewer.current?.play(Number(e.target.value)); }}><option value={-1}>기본 자세</option>{clips.map(c => <option key={c.index} value={c.index}>{c.name}</option>)}</select></label>}
    {error && <p role="alert">{error}</p>}
    <div className="standard-renders">{['front', 'side', 'back', 'motion'].map(view => { const image = item.artifacts.find(a => a.name === `${view}.png`); return image && <a key={view} href={image.url} target="_blank" rel="noreferrer"><img src={image.url} alt={`${view} 검수`} /><span>{view}</span></a>; })}</div>
    <div className="standard-downloads">{item.artifacts.map(a => <a key={a.name} href={a.url} download>{a.name}</a>)}</div>
  </section>;
}

function Review({ item, busy, run }: { item: StandardItem; busy: boolean; run: (task: () => Promise<StandardItem>) => void }) {
  const [checks, setChecks] = useState([false, false, false]), [notes, setNotes] = useState('');
  return <fieldset disabled={busy}><legend>이 버전의 기준 몸 검수</legend><p>위 정면·측면·후면과 실제 동작을 확인한 뒤 고정하세요. 기술 검사 통과만으로 승인되지 않습니다.</p>
    {['두피·몸이 완전하고 헤어·교체 의상이 제거됨', '중립 표정과 A-pose 확인', '팔·다리·머리 동작 확인'].map((label, i) => <label key={label}><input type="checkbox" checked={checks[i]} onChange={e => setChecks(checks.map((v, j) => i === j ? e.target.checked : v))} />{label}</label>)}
    <label>검수 메모<textarea value={notes} onChange={e => setNotes(e.target.value)} /></label>
    <button disabled={!checks.every(Boolean) || notes.trim().length < 5} onClick={() => run(() => standardApi.review(item.id, { model_sha256: item.model_sha256, decision: 'approved', bald_complete_body: checks[0], neutral_apose: checks[1], motion_checked: checks[2], notes }))}>검수한 몸·골격 고정</button>
  </fieldset>;
}

function PartForm({ base, shapes, busy, run }: { base: StandardItem; shapes: StandardItem[]; busy: boolean; run: (task: () => Promise<StandardItem>) => void }) {
  const [name, setName] = useState('새 상의'), [file, setFile] = useState<File>();
  const [type, setType] = useState('top'), [bone, setBone] = useState(base.result?.bones[0] || '');
  const [anchors, setAnchors] = useState('[\n  {"name":"neck","source":[0,0.8,0],"target":[0,0.8,0]},\n  {"name":"left","source":[0.2,0.6,0],"target":[0.2,0.6,0]},\n  {"name":"right","source":[-0.2,0.6,0],"target":[-0.2,0.6,0]}\n]');
  const [side, setSide] = useState('shoeLeft');
  const [shapeId, setShapeId] = useState('');
  const shape = shapes.find(s => s.id === shapeId);
  const transfer = ['top', 'pants', 'boot'].includes(type);
  return <fieldset disabled={busy}><legend>3. 파츠 치수·공용 골격 연결</legend>
    <p>생성한 파츠 GLB를 가져와 착용 기준점 3개 이상을 맞춥니다. 좌표는 미터 단위 X 오른쪽·Y 위·Z 앞입니다. 아래 예시 좌표를 실제 파츠와 몸의 측정값으로 바꾸세요.</p>
    <label>파츠 이름<input value={name} onChange={e => setName(e.target.value)} /></label>
    <label>파츠 GLB<input type="file" accept=".glb" onChange={e => setFile(e.target.files?.[0])} /></label>
    <label>또는 생성한 Meshy 형상<select value={shapeId} onChange={e => setShapeId(e.target.value)}><option value="">업로드한 GLB 사용</option>{shapes.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
    <label>파츠 유형<select value={type} onChange={e => setType(e.target.value)}>{Object.entries({ top: '상의', pants: '바지', skirt: '치마', hair: '짧은 헤어', hat: '모자', shoe: '단단한 신발', boot: '부츠', accessory: '소품' }).map(([v, label]) => <option key={v} value={v}>{label}</option>)}</select></label>
    {['shoe', 'boot'].includes(type) && <label>신발 방향<select value={side} onChange={e => setSide(e.target.value)}><option value="shoeLeft">왼쪽</option><option value="shoeRight">오른쪽</option></select></label>}
    {transfer ? <p>기준 몸 표면의 가중치 전달 · 동일 골격 사용</p> : <label>연결 본<select value={bone} onChange={e => setBone(e.target.value)}>{base.result?.bones.map(b => <option key={b}>{b}</option>)}</select></label>}
    <details><summary>기준 몸의 본 위치 보기</summary><pre>{JSON.stringify(base.result?.bone_heads_gltf, null, 2)}</pre></details>
    <label>착용 기준점<textarea aria-label="착용 기준점" rows={8} value={anchors} onChange={e => setAnchors(e.target.value)} /></label>
    <button disabled={(!file && !shape) || !name.trim()} onClick={() => run(async () => {
      const parsed = JSON.parse(anchors); const asset = shape ? { id: shape.result!.model_asset! } : await standardApi.upload(file!, 'glb');
      const slot = ['pants', 'skirt'].includes(type) ? 'bottom' : ['shoe', 'boot'].includes(type) ? side : type;
      return standardApi.create('parts', { name, base_id: base.id, base_sha256: base.model_sha256, model_asset: asset.id, shape_id: shape?.id || null, image_ids: shape?.contract.image_ids || [], slot, garment_type: type, binding: transfer ? 'transfer' : 'rigid', bone: transfer ? null : bone, anchors: parsed });
    })}>기준 몸에 맞춰 파츠 연결</button>
  </fieldset>;
}

function ShapeForm({ base, images, busy, run }: { base: StandardItem; images: StandardItem[]; busy: boolean; run: (task: () => Promise<StandardItem>) => void }) {
  const [selected, setSelected] = useState<string[]>([]), [name, setName] = useState('새 파츠 형상');
  const ordered = selected.map(id => images.find(i => i.id === id)!).filter(Boolean).sort((a, b) => a.contract.view === 'front' ? -1 : b.contract.view === 'front' ? 1 : 0);
  const valid = ordered.length >= 1 && ordered.length <= 4 && ordered[0].contract.view === 'front' && new Set(ordered.map(i => i.contract.object_key)).size === 1 && new Set(ordered.map(i => i.contract.view)).size === ordered.length;
  return <fieldset disabled={busy}><legend>시안으로 Meshy 파츠 생성</legend><p>한 물체의 정면·측면·후면을 선택하세요. Meshy 7 생성 최대 1회가 청구됩니다. 파츠별 리깅은 실행하지 않습니다.</p>
    <label>형상 이름<input value={name} onChange={e => setName(e.target.value)} /></label>
    {images.map(i => <label key={i.id}><input type="checkbox" checked={selected.includes(i.id)} onChange={e => setSelected(e.target.checked ? [...selected, i.id] : selected.filter(id => id !== i.id))} />{i.name}</label>)}
    <button disabled={!valid || !name.trim()} onClick={() => run(() => standardApi.create('shapes', { name, base_id: base.id, base_sha256: base.model_sha256, image_ids: ordered.map(i => i.id), max_new_tasks: 1 }))}>Meshy 7 파츠 생성 · 유료 1회</button>
  </fieldset>;
}

function ImageForm({ base, busy, run }: { base: StandardItem; busy: boolean; run: (task: () => Promise<StandardItem>) => void }) {
  const [file, setFile] = useState<File>(), [view, setView] = useState('front'), [key, setKey] = useState('cardigan');
  const [crop, setCrop] = useState('0,0,2048,2048');
  return <fieldset disabled={busy}><legend>2. 같은 캔버스의 파츠 시안</legend>
    <p>기준 몸의 정면·측면·후면 렌더를 내려받아 그 위에서 디자인하세요. 원본은 2048 × 2048px, 정수리 y=300, 발바닥 y=1800, 중심 x=1024를 유지합니다.</p>
    <label>동일 물체 식별자<input value={key} onChange={e => setKey(e.target.value)} /></label>
    <label>시점<select value={view} onChange={e => setView(e.target.value)}><option value="front">정면</option><option value="side">측면</option><option value="back">후면</option></select></label>
    <label>2048px 파츠 PNG<input type="file" accept="image/png" onChange={e => setFile(e.target.files?.[0])} /></label>
    <label>잘라내기 x,y,너비,높이<input value={crop} onChange={e => setCrop(e.target.value)} /></label>
    <button disabled={!file} onClick={() => run(async () => { const asset = await standardApi.upload(file!, 'png'); return standardApi.image({ base_id: base.id, base_sha256: base.model_sha256, image_asset: asset.id, object_key: key, view, crop: crop.split(',').map(Number), export_size: 1024 }); })}>원본 좌표와 생성용 시안 저장</button>
  </fieldset>;
}

export function StandardFactory() {
  const live = useLiveCharacters();
  const [items, setItems] = useState<StandardItem[]>([]), [id, setId] = useState(new URLSearchParams(location.search).get('item') || '');
  const [baseId, setBaseId] = useState(''), [characterId, setCharacterId] = useState('');
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [connection, setConnection] = useState('');
  const [selected, setSelected] = useState<string[]>([]), [outfitName, setOutfitName] = useState('새 조합');
  const [texture, setTexture] = useState<File>(), [material, setMaterial] = useState(''), [uvConfirmed, setUvConfirmed] = useState(false);
  const [taskId, setTaskId] = useState('');
  const busyRef = useRef(false), active = useRef(true);
  const item = items.find(i => i.id === id);
  const bases = items.filter(i => i.kind === 'base' && i.status === 'approved');
  const base = bases.find(i => i.id === baseId) || bases[0];
  const parts = items.filter(i => i.kind === 'part' && i.status === 'review_required' && i.contract.base_id === base?.id);
  async function refresh() { const result = await standardApi.list(); if (active.current) { setItems(result.items); setConnection(''); } }
  useEffect(() => {
    active.current = true; let running = false;
    const reload = async () => { if (running || document.hidden) return; running = true; try { await refresh(); } catch (e) { if (active.current) setConnection((e as Error).message); } finally { running = false; } };
    void reload(); const timer = setInterval(() => void reload(), 2000); window.addEventListener('online', reload);
    return () => { active.current = false; clearInterval(timer); window.removeEventListener('online', reload); };
  }, []);
  function select(value: string) { setId(value); const url = new URL(location.href); url.searchParams.set('item', value); history.replaceState(null, '', url); }
  async function run(task: () => Promise<StandardItem>) {
    if (busyRef.current) return; busyRef.current = true; setBusy(true); setError('');
    try { const result = await task(); if (active.current) { select(result.id); await refresh(); } }
    catch (e) { if (active.current) setError((e as Error).message); }
    finally { busyRef.current = false; if (active.current) setBusy(false); }
  }
  const character = live.characters.find(c => c.id === characterId);
  return <main className="standard-page">
    <header><a href="/avatar.html">gaesup · 이미지 공장</a><h1>고정 몸 · 공용 골격 공장</h1><a href="/">몸 생성·리깅 라이브러리</a></header>
    <p>한 번 검수한 몸으로 템플릿을 만들고, 파츠와 조합만 새 버전으로 저장합니다.</p>
    {(error || connection || live.failure) && <p className="standard-error" role="alert">{error || connection || live.failure}</p>}
    {standardApi.pending() && <button disabled={busy} onClick={() => void run(() => standardApi.create('', {}))}>응답을 잃은 요청 복구</button>}
    <div className="standard-layout"><aside>
      <fieldset disabled={busy}><legend>1. 기준 몸 등록</legend><p>대머리·중립 A-pose의 리깅 GLB와 동작을 준비하세요. 원본을 보존하고 높이 1.20m의 새 기준 버전을 만듭니다.</p>
        <label>기준 몸 GLB 가져오기<input type="file" accept=".glb" onChange={e => { const file = e.target.files?.[0]; if (!file || busyRef.current) return; void run(async () => { let c = await api.create(file.name.replace(/\.glb$/i, ''), 1.2); c = await api.upload(c, file, 'model'); await live.refresh(); setCharacterId(c.id); return standardApi.create('bases', { character_id: c.id, source_sha256: c.model_sha256, name: c.name, height_m: 1.2 }); }); e.target.value = ''; }} /></label>
        <label>등록된 몸<select value={characterId} onChange={e => setCharacterId(e.target.value)}><option value="">리깅된 몸 선택</option>{live.characters.filter(c => c.model_id).map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
        <button disabled={!character?.model_sha256} onClick={() => void run(() => standardApi.create('bases', { character_id: character!.id, source_sha256: character!.model_sha256, name: character!.name, height_m: 1.2 }))}>기준 몸 템플릿 생성</button>
      </fieldset>
      <h2>저장된 버전</h2>{items.length === 0 && <p>아직 등록된 기준 몸이 없습니다.</p>}
      <div className="standard-items">{items.map(i => <button key={i.id} aria-pressed={i.id === id} onClick={() => select(i.id)}><strong>{i.name}</strong><span>{kinds[i.kind]} · {statuses[i.status] || i.status}</span></button>)}</div>
    </aside><div>
      {item && <section><h2>{item.name}</h2><p role="status">{statuses[item.status] || item.status}{item.result ? ` · ${item.result.bones?.length || 0}개 본` : ''}</p>{item.error && <p role="alert">{item.error}</p>}
        {item.review?.notes && <p className={item.review.decision === 'changes_requested' ? 'standard-error' : ''}>{item.review.notes}</p>}
        {item.next_actions.includes('recover') && <button disabled={busy} onClick={() => void run(() => standardApi.recover(item.id))}>중단된 실행 증거 복구</button>}
        {item.provider && <p>{item.provider.model}{item.kind === 'shape' && <> · {item.provider.status} · {item.provider.progress || 0}% · {item.provider.task_id || 'task ID 대기'}</>}</p>}
        {item.next_actions.includes('resume_design') && <button disabled={busy} onClick={() => void run(() => standardApi.resumeDesign(item.id))}>시안 수락·응답 기록 이어가기</button>}
        {item.next_actions.includes('poll') && <button disabled={busy} onClick={() => void run(() => standardApi.poll(item.id))}>기존 Meshy 작업 조회·다운로드</button>}
        {item.next_actions.includes('resume_submission') && <button disabled={busy} onClick={() => void run(() => standardApi.resumeSubmission(item.id))}>수락한 제출 이어가기</button>}
        {item.next_actions.includes('recover_task') && <label>응답을 잃은 Meshy task ID<input value={taskId} onChange={e => setTaskId(e.target.value)} /><button disabled={busy || !/^[a-zA-Z0-9_-]{1,100}$/.test(taskId)} onClick={() => void run(() => standardApi.recoverTask(item.id, taskId))}>기존 task ID로 복구</button></label>}
        {item.kind !== 'design' && item.artifacts.length > 0 && <Preview key={`preview-${item.id}`} item={item} />}
        {item.kind === 'design' && item.status === 'design_review_required' && items.some(b => b.id === item.contract.base_id) && <AlignDesign key={`align-${item.id}`} item={item} base={items.find(b => b.id === item.contract.base_id)!} busy={busy} run={task => void run(task)} />}
        {item.kind === 'base' && item.status === 'review_required' && <Review key={`review-${item.id}`} item={item} busy={busy} run={task => void run(task)} />}
        {item.kind === 'part' && item.result && <p>최대 표면 거리 {item.result.fit.max_surface_distance_m?.toFixed(4)}m · 관통 의심 정점 {item.result.fit.possible_inside_vertices}. 동작과 외형 검수가 필요합니다.</p>}
      </section>}
      <label>생산 기준 몸<select value={base?.id || ''} onChange={e => { setBaseId(e.target.value); setSelected([]); setTexture(undefined); setMaterial(''); setUvConfirmed(false); }}><option value="">승인한 기준 몸 선택</option>{bases.map(b => <option key={b.id} value={b.id}>{b.name} · {b.id.slice(0, 6)}</option>)}</select></label>
      <WardrobeBatchPanel base={base} select={select} characters={live.characters} />
      {base && <StandardWardrobe key={`wardrobe-${base.id}`} base={base} parts={parts} selected={selected} onSelection={setSelected} />}
      {base ? <><GenerateDesign key={`design-${base.id}`} base={base} images={items.filter(i => i.kind === 'image' && i.contract.base_id === base.id)} busy={busy} run={task => void run(task)} /><ImageForm key={`image-${base.id}`} base={base} busy={busy} run={task => void run(task)} /><ShapeForm key={`shape-${base.id}`} base={base} images={items.filter(i => i.kind === 'image' && i.contract.base_id === base.id)} busy={busy} run={task => void run(task)} /><PartForm key={`part-${base.id}`} base={base} shapes={items.filter(i => i.kind === 'shape' && i.status === 'model_ready' && i.contract.base_id === base.id)} busy={busy} run={task => void run(task)} />
        <fieldset disabled={busy}><legend>4. 같은 몸의 조합 만들기</legend><label>조합 이름<input value={outfitName} onChange={e => setOutfitName(e.target.value)} /></label>
          <p>위 옷 갈아입기에서 선택한 의상을 파일로 저장합니다.</p>
          {selected.length ? <ul>{parts.filter(p => selected.includes(p.id)).map(p => <li key={p.id}>{p.name} · {p.contract.slot}</li>)}</ul> : <p>먼저 착용할 의상을 선택하세요.</p>}
          <details><summary>얼굴·옷의 UV 텍스처 바꾸기</summary><p>내려받은 UV 템플릿에 맞춘 PNG를 사용하세요. 원본 메시·골격·가중치는 유지합니다.</p>
            <label>변경할 UV 재질<select value={material} onChange={e => setMaterial(e.target.value)}><option value="">변경 없음</option>{base.result?.materials?.filter(m => m.has_uv).map(m => <option key={`base:${m.index}`} value={`base:${m.index}`}>몸 · {m.name}</option>)}{parts.filter(p => selected.includes(p.id)).flatMap(p => p.result?.part_materials?.filter(m => m.has_uv).map(m => <option key={`${p.id}:${m.index}`} value={`${p.id}:${m.index}`}>{p.name} · {m.name}</option>) || [])}</select></label>
            <label>UV 텍스처 PNG<input type="file" accept="image/png" onChange={e => setTexture(e.target.files?.[0])} /></label>
            <label><input type="checkbox" checked={uvConfirmed} onChange={e => setUvConfirmed(e.target.checked)} />선택한 재질과 동일한 UV 배치 확인</label>
          </details>
          <button disabled={!selected.length || (material !== '' && (!texture || !uvConfirmed))} onClick={() => void run(async () => {
            const [scope, materialIndex] = material.split(':');
            const textures = material !== '' ? [{ material_index: Number(materialIndex), part_id: scope === 'base' ? null : scope, image_asset: (await standardApi.upload(texture!, 'png')).id, uv_layout_confirmed: true }] : [];
            return standardApi.create('assemblies', { base_id: base.id, base_sha256: base.model_sha256, part_ids: selected, name: outfitName, textures });
          })}>선택한 파츠로 조합 저장</button>
        </fieldset></> : <p>기준 몸의 외형·동작을 검수하고 고정하면 파츠 제작을 시작할 수 있습니다.</p>}
    </div></div>
  </main>;
}
