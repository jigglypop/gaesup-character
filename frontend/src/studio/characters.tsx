import { useCallback, useEffect, useRef, useState } from 'react';
import { api, type Character } from '../api';
import type { ModelViewer } from '../viewer';
import { StudioIcon } from './icons';

export const pipelineNames: Record<string, string> = { ready: '준비됨', blocked: '작업 대기', in_progress: '작업 중', review_required: '검수 대기', approved: '승인됨' };

export function useLiveCharacters() {
  const [characters, setCharacters] = useState<Character[]>([]);
  const [failure, setFailure] = useState('');
  const [loading, setLoading] = useState(true);
  const active = useRef(true), running = useRef(false);
  const refresh = useCallback(async () => {
    if (running.current) return;
    running.current = true;
    try {
      const result = await api.list();
      if (active.current) { setCharacters(result.characters); setFailure(''); }
    } catch (error) { if (active.current) setFailure((error as Error).message); }
    finally { running.current = false; if (active.current) setLoading(false); }
  }, []);
  useEffect(() => {
    active.current = true; void refresh();
    const interval = setInterval(() => { if (!document.hidden) void refresh(); }, 5000);
    const reconnect = () => { if (!document.hidden) void refresh(); };
    window.addEventListener('online', reconnect); document.addEventListener('visibilitychange', reconnect);
    return () => { active.current = false; clearInterval(interval); window.removeEventListener('online', reconnect); document.removeEventListener('visibilitychange', reconnect); };
  }, [refresh]);
  return { characters, loading, failure, refresh };
}

export function CharacterPreview({ character }: { character: Character }) {
  const mount = useRef<HTMLDivElement>(null), viewer = useRef<ModelViewer | null>(null);
  const [loading, setLoading] = useState(true), [failure, setFailure] = useState('');
  const [clips, setClips] = useState<{ index: number; name: string }[]>([]);
  const [animation, setAnimation] = useState(-1);
  const artifact = character.artifacts.find(item => item.id === character.model_id);
  const reference = character.artifacts.find(item => item.id === 'reference');
  useEffect(() => {
    setFailure(''); setLoading(true); setClips([]); setAnimation(-1);
    if (!artifact) { setLoading(false); return; }
    let disposed = false, instance: ModelViewer | undefined;
    void import('../viewer').then(async ({ ModelViewer }) => {
      if (disposed) return;
      instance = new ModelViewer(mount.current!, 'studio'); viewer.current = instance;
      const animations = await instance.load(artifact.url);
      if (!disposed) { setClips(animations); setLoading(false); }
    }).catch(error => { if (!disposed) { setFailure((error as Error).message); setLoading(false); } });
    return () => { disposed = true; instance?.dispose(); viewer.current = null; };
  }, [artifact?.url, character.model_sha256]);
  return <div className="source-preview-scene">
    <div ref={mount} className="source-model-viewer" />
    {!artifact && <div className="source-input-preview">{reference && <img src={reference.url} alt={`${character.name} 입력 이미지`} />}<strong>3D 결과 대기 중</strong><p>등록된 소스입니다. 라이브러리에서 다음 작업을 진행하세요.</p></div>}
    {loading && <div className="scene-loading">3D 결과를 불러오는 중…</div>}
    {failure && <p role="alert" className="scene-error">{failure}</p>}
    {artifact && !loading && !failure && <label className="source-animation">동작<select aria-label="캐릭터 결과 동작" value={animation} onChange={event => { const value = Number(event.target.value); setAnimation(value); viewer.current?.play(value); }}><option value={-1}>기본 자세</option>{clips.map(clip => <option key={clip.index} value={clip.index}>{clip.name}</option>)}</select></label>}
  </div>;
}

export function CharacterInspector({ character }: { character: Character }) {
  const model = character.artifacts.find(item => item.id === character.model_id);
  const stages = [
    { label: '소스 등록', value: character.artifacts.some(item => item.id === 'reference' || item.id === 'imported') ? '등록됨' : '입력 대기' },
    { label: '리깅', value: ({ meshy: 'Meshy rig', local_fallback: '로컬 rig · 검수 필요', unknown: '확인 전' } as Record<string, string>)[character.rig_origin] || character.rig_origin },
    { label: '파츠 분리', value: character.model_id === 'parts_model' ? '결과 있음' : '대기' },
    { label: '외형 검수', value: character.review.decision === 'approved' ? '승인 기록 있음' : character.review.decision === 'changes_requested' ? '수정 요청' : '미승인' },
  ];
  return <div className="character-inspector">
    <span className="panel-kicker">CHARACTER PIPELINE</span><h2>{character.name}</h2><span className={`pipeline-status ${character.pipeline_status}`}>{pipelineNames[character.pipeline_status] || character.pipeline_status}</span>
    <div className="stage-list">{stages.map((stage, index) => <div className="stage-row" key={stage.label}><span className="stage-number">0{index + 1}</span><div><span>{stage.label}</span><strong>{stage.value}</strong></div></div>)}</div>
    {character.operation && <div className="job-summary"><span>최근 작업</span><strong>{character.operation.action_id}</strong><small>{({ succeeded: '완료', running: '진행 중', accepted: '수락됨', failed: '실패', recovery_required: '복구 필요' } as Record<string, string>)[character.operation.status] || character.operation.status}</small></div>}
    {character.provider.progress != null && <label className="provider-progress">Provider {character.provider.progress}%<progress value={character.provider.progress} max={100} /></label>}
    {character.problems.map(problem => <p className="pipeline-problem" key={problem.code}>{problem.message}</p>)}
    {character.operation?.error && <p className="pipeline-problem">{character.operation.error.message}</p>}
    {character.inspection.metrics && <div className="model-metrics"><span><b>{character.inspection.metrics.triangles.toLocaleString()}</b>삼각형</span><span><b>{character.inspection.metrics.joints.length}</b>관절</span><span><b>{character.inspection.metrics.animations.length}</b>동작</span></div>}
    <a className="studio-primary continue-work" href={`/#${encodeURIComponent(character.id)}`}>라이브러리에서 작업 이어가기 <StudioIcon name="arrow" size={17} /></a>
    {model && <a className="artifact-download" href={model.url} download={`${character.id}.glb`}><StudioIcon name="download" size={17} /> 현재 GLB 받기</a>}
    <p className="inspector-footnote">이 모델은 저장된 캐릭터 작업 결과입니다. 공통 아바타 파츠로의 자동 변환은 아직 연결되지 않았습니다.</p>
  </div>;
}
