import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from 'react';
import { createRoot } from 'react-dom/client';
import { useAssetStore, type AssetRecord } from 'gaesup-world/assets';
import { avatarApi, createAvatarPersistence, type SavedAvatar } from './avatar/api';
import { avatarManifestFromRecord } from './avatar/core/manifest';
import { AVATAR_SLOTS, type AvatarSlot, type AvatarState } from './avatar/core/types';
import type { AvatarRuntime } from './avatar/runtime/AvatarRuntime';
import { AvatarViewport } from './avatar/viewport';
import { CharacterInspector, CharacterPreview, pipelineNames, useLiveCharacters } from './studio/characters';
import { ImplementationStatus } from './studio/status';
import { PieceIcon, StudioIcon } from './studio/icons';
import './avatar-page.css';

const labels: Record<AvatarSlot, string> = { body: '몸', face: '얼굴', hair: '헤어', top: '상의', bottom: '하의', onepiece: '원피스', shoes: '신발', hat: '모자', ear: '귀', back: '등', bag: '가방', hand: '손 소품', faceAccessory: '얼굴 장식', neckAccessory: '목 장식' };
const poses = { idle: 'Idle', walk: 'Walk', run: 'Run', jump: 'Jump', sit: 'Sit', armsUp: 'Arms Up', crouch: 'Crouch' };
const empty: AvatarState = { body: '', equipment: {} };
const idleSubscribe = () => () => {};
const getEmpty = () => empty;

function Studio({ assets, saved }: { assets: AssetRecord[]; saved: SavedAvatar }) {
  const [runtime, setRuntime] = useState<AvatarRuntime | null>(null);
  const [slot, setSlot] = useState<AvatarSlot>('hair');
  const [busy, setBusy] = useState(false), busyRef = useRef(false);
  const [message, setMessage] = useState('아바타를 불러오는 중…'), [error, setError] = useState(false);
  const [backend, setBackend] = useState('initializing');
  const [pose, setPose] = useState('idle');
  const [lod, setLod] = useState(0);
  const [sourceId, setSourceId] = useState(new URLSearchParams(location.search).get('character') || '');
  const [statusOpen, setStatusOpen] = useState(false);
  const live = useLiveCharacters();
  const source = live.characters.find(character => character.id === sourceId);
  const [diagnostics, setDiagnostics] = useState<ReturnType<AvatarRuntime['getDiagnostics']>>();
  const persistence = useRef<ReturnType<typeof createAvatarPersistence> | null>(null);
  const state = useSyncExternalStore(runtime?.subscribe ?? idleSubscribe, runtime?.getSnapshot ?? getEmpty, getEmpty);
  const ready = useCallback((avatar: AvatarRuntime) => {
    setRuntime(avatar); persistence.current = createAvatarPersistence(avatar, saved.revision);
    setError(false); setMessage(persistence.current.hasPending() ? '응답이 확인되지 않은 저장이 있습니다. 저장 재시도로 복구하세요.' : '파츠를 선택하면 3D 아바타에 바로 반영됩니다.');
  }, [saved.revision]);
  const failed = useCallback((failure: Error) => { setError(true); setMessage(failure.message); }, []);
  useEffect(() => {
    if (!runtime) return;
    const timer = setInterval(() => setDiagnostics(runtime.getDiagnostics()), 200);
    return () => clearInterval(timer);
  }, [runtime]);
  async function act(work: () => Promise<unknown> | void, success: string) {
    if (busyRef.current) return;
    busyRef.current = true; setBusy(true);
    try { await work(); setError(false); setMessage(success); }
    catch (failure) { failed(failure instanceof Error ? failure : new Error(String(failure))); }
    finally { busyRef.current = false; setBusy(false); }
  }
  const items = assets.filter(asset => avatarManifestFromRecord(asset).slot === slot);
  const selected = slot === 'body' ? state.body : state.equipment[slot];
  const slots = AVATAR_SLOTS.filter(candidate => assets.some(asset => avatarManifestFromRecord(asset).slot === candidate));
  function selectSource(id: string) {
    setSourceId(id);
    const url = new URL(location.href);
    if (id) url.searchParams.set('character', id); else url.searchParams.delete('character');
    history.replaceState(null, '', url);
  }
  return <>
    <header className="atelier-header"><a href="/" className="atelier-brand"><span className="brand-mark"><StudioIcon name="cube" size={23} /></span>gaesup<span className="brand-studio">studio</span></a><nav><a href="/avatar.html" aria-current="page">스튜디오</a><a href="/">캐릭터 라이브러리</a></nav><div className="header-end"><span className="local-label"><span className={`live-dot ${live.failure ? 'offline' : ''}`} />{live.loading ? '연결 중' : live.failure ? '재연결 대기' : '로컬 API 연결됨'}</span><button className="status-button" onClick={() => setStatusOpen(true)}><StudioIcon name="activity" size={17} /> 구현 현황</button><span className="profile-avatar">GW</span></div></header>
    <main className="avatar-studio">
      <aside className="project-sidebar">
        <div className="workspace-heading"><span className="workspace-avatar"><StudioIcon name="layers" /></span><div><strong>Avatar workspace</strong><small>로컬 프로젝트</small></div></div>
        <a className="sidebar-create" href="/"><span>＋</span> 캐릭터 가져오기 <StudioIcon name="arrow" size={15} /></a>
        <div className="sidebar-section-title"><span>MY ASSETS</span><button className="icon-button" aria-label="캐릭터 목록 새로고침" onClick={() => void live.refresh()}><StudioIcon name="refresh" size={15} /></button></div>
        <button className={`source-card modular-card ${!sourceId ? 'selected' : ''}`} aria-label="모듈형 아바타 선택" onClick={() => selectSource('')}><span className="source-thumb fixture-thumb"><StudioIcon name="cube" size={25} /></span><span><strong>모듈형 아바타</strong><small>{assets.length}개 파츠 · 런타임 데모</small></span><span className="selection-dot" /></button>
        <div className="source-list" aria-label="서버 캐릭터 목록">{live.characters.map(character => {
          const thumbnail = character.artifacts.find(item => item.id === 'rest_render') || character.artifacts.find(item => item.id === 'reference');
          return <button key={character.id} className={`source-card ${sourceId === character.id ? 'selected' : ''}`} aria-pressed={sourceId === character.id} onClick={() => selectSource(character.id)}><span className="source-thumb">{thumbnail ? <img src={thumbnail.url} alt="" loading="lazy" /> : <StudioIcon name="cube" />}</span><span><strong>{character.name}</strong><small><i className={`source-dot ${character.pipeline_status}`} />{pipelineNames[character.pipeline_status] || character.pipeline_status}</small></span></button>;
        })}</div>
        {live.loading && <p className="sidebar-note">캐릭터를 불러오는 중…</p>}
        {!live.loading && !live.failure && !live.characters.length && <p className="sidebar-note">등록된 캐릭터가 없습니다. 라이브러리에서 소스를 가져오세요.</p>}
        {live.failure && <p className="sidebar-error" role="alert">캐릭터 목록 연결이 끊겼습니다. 마지막 상태를 표시하며 자동으로 다시 연결합니다.</p>}
        <div className="sidebar-bottom"><span className="panel-kicker">YOUR PIPELINE</span><div className="mini-flow"><span>소스</span><span>→</span><span>파츠</span><span>→</span><span>아바타</span></div><p>작업 결과와 실시간 조합을<br />한 화면에서 확인하세요.</p><button onClick={() => setStatusOpen(true)}>구현 범위 확인 <StudioIcon name="arrow" size={15} /></button></div>
      </aside>
      <div className="studio-workbench">
      <div className="studio-heading"><div><div className="breadcrumbs">Workspace <span>/</span> {source ? 'Character pipeline' : 'Modular avatar'}</div><h1>{source?.name || '나만의 아바타를 조립하세요.'}</h1></div><div className="save-actions"><button disabled={!runtime || busy || !!source} onClick={() => void act(() => persistence.current!.load(), '서버의 장착 상태를 불러왔습니다.')}><StudioIcon name="refresh" size={15} /> 서버에서 불러오기</button><button className="accent" disabled={!runtime || busy || !!source} onClick={() => void act(() => persistence.current!.save(), '장착 상태를 서버에 저장했습니다.')}><StudioIcon name="check" size={16} />{persistence.current?.hasPending() ? '저장 재시도' : '장착 저장'}</button></div></div>
      <div className="studio-columns">
        <section className="avatar-preview" aria-label="아바타 미리보기" data-skeleton-id={diagnostics?.skeletonId} data-animation={diagnostics?.animation} data-mixer-time={diagnostics?.mixerTime} data-lod={diagnostics?.lod}>
          <div className="preview-caption"><div className="viewport-tabs"><span className="active"><StudioIcon name="cube" size={15} /> 3D 뷰</span><span>{source ? '캐릭터 작업 결과' : '파츠 조합'}</span></div>{!source && <span className="renderer-chip"><i />{backend === 'webgpu' ? 'WebGPU' : backend === 'webgl-fallback' ? 'WebGL 호환 모드' : '초기화 중'}</span>}</div>
          <div className="scene-stage">
            <div className={`modular-scene ${source ? 'scene-hidden' : ''}`} aria-hidden={!!source}><AvatarViewport initial={saved.state} onReady={ready} onError={failed} onBackend={setBackend} /></div>
            {source && <CharacterPreview character={source} />}
            {!source && <><div className="scene-label"><span>SD_NEUTRAL_V1</span><strong>Modular Avatar</strong><small>{diagnostics ? `${diagnostics.parts} parts equipped` : 'Preparing your avatar…'}</small></div><div className="scene-toolbar"><button className="icon-button" title="시점 초기화" aria-label="시점 초기화" onClick={() => document.querySelector('.avatar-viewport')?.dispatchEvent(new Event('avatar:reset-view'))}><StudioIcon name="focus" size={18} /></button><button className="icon-button" title="구현 현황" aria-label="뷰포트 구현 현황" onClick={() => setStatusOpen(true)}><StudioIcon name="activity" size={18} /></button></div><div className="axis-gizmo" aria-hidden="true"><span>Y</span><i /><b>X</b><small>Z</small></div></>}
          </div>
          {!source && <><div className="preview-controls"><span>드래그하여 회전 · 스크롤하여 확대</span><label>디테일<select aria-label="디테일" value={lod} disabled={!runtime || busy} onChange={event => { const level = Number(event.target.value); void act(async () => { await runtime!.setLOD(level); setLod(level); }, '디테일을 변경했습니다.'); }}><option value={0}>높음 · LOD 0</option><option value={1}>가벼움 · LOD 1</option></select></label></div>
          <div className="animation-dock"><div><span className="panel-kicker">MOTION PREVIEW</span><span className="motion-count">{diagnostics ? `${diagnostics.animationTime.toFixed(1)} / ${diagnostics.animationDuration.toFixed(1)} s` : '7 motions'}</span></div><div className="pose-bar" aria-label="동작 확인">{Object.entries(poses).map(([name, label]) => <button key={name} aria-pressed={pose === name} disabled={!runtime || busy} onClick={() => { runtime!.playAnimation(name); setPose(name); }}>{label}</button>)}</div><div className="timeline-track"><span className="timeline-marker" style={{ left: `${diagnostics?.animationDuration ? (diagnostics.animationTime / diagnostics.animationDuration) * 100 : 0}%` }} /><span /><span /><span /><span /><span /><span /><span /></div></div></>}
          {source && <div className="source-context"><span className="source-dot" />서버 산출물 · {source.model_id || '입력 이미지'}<a href={`/#${encodeURIComponent(source.id)}`}>검수 화면으로 이동 <StudioIcon name="arrow" size={14} /></a></div>}
        </section>
        <section className="wardrobe-panel" aria-label={source ? '캐릭터 작업 상태' : '파츠 선택'}>
          {source ? <CharacterInspector character={source} /> : <>
          <div className="wardrobe-heading"><div><span className="panel-kicker">CUSTOMIZE</span><h2>파츠 라이브러리</h2></div><span>{assets.length}<small>ASSETS</small></span></div>
          <div className="slot-tabs" role="tablist" aria-label="장착 슬롯">{slots.map(candidate => <button key={candidate} role="tab" aria-selected={candidate === slot} onClick={() => setSlot(candidate)}>{labels[candidate]}</button>)}</div>
          <div className="pieces-heading"><span>{labels[slot]}</span><small>{items.length}개의 파츠</small></div>
          <div className="pieces">{items.map(asset => <button key={asset.id} className="piece" aria-pressed={selected === asset.id} disabled={!runtime || busy} onClick={() => void act(() => runtime!.equip(slot, asset.id), `${asset.name} 장착 완료`)}>
            <span className="piece-swatch"><PieceIcon slot={slot} color={asset.colors?.primary} />{selected === asset.id && <span className="piece-check"><StudioIcon name="check" size={11} /></span>}</span><span className="piece-name">{asset.name}</span><span className="piece-state">{selected === asset.id ? '장착 중' : '선택하기'}</span>
          </button>)}</div>
          <button className="remove-piece" disabled={!runtime || busy || slot === 'body' || !selected} onClick={() => void act(() => runtime!.unequip(slot), `${labels[slot]} 장착 해제`)}>선택 슬롯 해제</button>
          <div className="outfit"><h3>현재 조합 <span>{Object.keys(state.equipment).length}</span></h3><div>{Object.entries(state.equipment).map(([key, id]) => <span key={key} data-equipped-slot={key} data-asset-id={id}><i style={{ background: assets.find(asset => asset.id === id)?.colors?.primary }} />{labels[key as AvatarSlot]} · {assets.find(asset => asset.id === id)?.name ?? id}</span>)}</div></div>
          <div className="contract-note"><StudioIcon name="layers" size={19} /><div><strong>하나의 rig, 이어지는 동작</strong><p>옷을 바꿔도 캐릭터의 스켈레톤과 애니메이션을 유지합니다.</p></div></div>
          </>}
        </section>
      </div>
      <div className="studio-footer"><p role={error && !source ? 'alert' : 'status'} className={`avatar-message ${error && !source ? 'error' : ''}`}><span className="live-dot" />{source ? `${source.name} · ${pipelineNames[source.pipeline_status] || source.pipeline_status}` : busy ? '변경 사항을 처리하는 중…' : message}</p><span>{source ? 'SOURCE ASSET' : 'MANUAL TEST ASSETS'}<span>·</span> LOCAL WORKSPACE</span></div>
      <p className="fixture-note">{source ? '실제 캐릭터의 작업 상태를 조회합니다. 기술 검사와 외형 승인은 별도로 확인합니다.' : '수동 제작한 기능 검증용 파츠입니다. 실제 생성 캐릭터의 의상 분리·외형 승인과는 별도로 확인합니다.'}</p>
      </div>
    </main>
    <ImplementationStatus open={statusOpen} onClose={() => setStatusOpen(false)} diagnostics={diagnostics} assets={assets.length} backend={backend} connected={!live.loading && !live.failure} />
  </>;
}

function App() {
  const [data, setData] = useState<{ assets: AssetRecord[]; saved: SavedAvatar }>();
  const [failure, setFailure] = useState('');
  async function load() {
    setFailure('');
    try {
      const [assets, saved] = await Promise.all([avatarApi.catalog(), avatarApi.read()]);
      useAssetStore.getState().registerAssets(assets);
      setData({ assets, saved });
    } catch (error) { setFailure((error as Error).message); }
  }
  useEffect(() => { void load(); }, []);
  return data ? <Studio {...data} /> : <main className="startup"><a href="/">← 캐릭터 라이브러리</a><h1>아바타 옷장</h1>{failure ? <><p role="alert">{failure}</p><button onClick={() => void load()}>연결 다시 시도</button></> : <p role="status">카탈로그와 저장 상태를 불러오는 중…</p>}</main>;
}

if (new URLSearchParams(location.search).get('view') === 'wardrobe') {
  createRoot(document.getElementById('app')!).render(<App />);
} else {
  void import('./factory/Factory').then(({ Factory }) => createRoot(document.getElementById('app')!).render(<Factory />));
}
