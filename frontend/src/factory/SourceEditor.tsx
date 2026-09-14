import { useEffect, useRef, useState } from 'react';
import type { Character } from '../api';
import type { ModelViewer } from '../viewer';
import type { FaceSelection } from './api';

const roles: Record<string, string> = { head: '얼굴·머리', hair: '헤어', hat: '모자', top: '상의', pants: '바지', skirt: '치마', dress: '원피스', shoes: '신발', body: '원본 몸', accessory: '액세서리', other: '보류 영역' };

export function SourceEditor({ character, onSelections }: { character: Character; onSelections(value: FaceSelection[]): void }) {
  const mount = useRef<HTMLDivElement>(null), viewer = useRef<ModelViewer | undefined>(undefined);
  const [loading, setLoading] = useState(true), [error, setError] = useState('');
  const [editing, setEditing] = useState(false), [role, setRole] = useState('hair'), [count, setCount] = useState(0);
  const [radius, setRadius] = useState(.025), [erase, setErase] = useState(false);
  const artifact = character.artifacts.find(item => item.id === character.model_id);
  const change = useRef(onSelections); change.current = onSelections;
  useEffect(() => {
    let disposed = false, instance: ModelViewer | undefined;
    setError(''); setLoading(true); setEditing(false); setCount(0); change.current([]);
    if (!artifact) { setLoading(false); return; }
    void import('../viewer').then(async ({ ModelViewer }) => {
      if (disposed) return;
      instance = new ModelViewer(mount.current!, 'studio'); viewer.current = instance;
      await instance.load(artifact.url);
      if (!disposed) setLoading(false);
    }).catch(error => { if (!disposed) { setError(error.message); setLoading(false); } });
    return () => { disposed = true; instance?.dispose(); viewer.current = undefined; };
  }, [artifact?.url, character.model_sha256]);
  useEffect(() => {
    viewer.current?.setEditing(editing, count => { setCount(count); change.current(viewer.current?.selections() || []); });
  }, [editing]);
  useEffect(() => { viewer.current?.setPaint({ role, radius, erase }); }, [role, radius, erase, editing]);
  return <div className="factory-source">
    <div ref={mount} className="factory-model" />
    {loading && <div className="factory-overlay">원본 모델을 불러오는 중…</div>}
    {error && <p role="alert" className="factory-overlay">{error}</p>}
    {!artifact && <div className="factory-overlay">GLB를 먼저 가져오세요.</div>}
    {artifact && <div className="factory-paint">
      <label><input type="checkbox" checked={editing} disabled={loading} onChange={event => setEditing(event.target.checked)} /> 파츠 영역 보정</label>
      {editing ? <>
        <select aria-label="보정할 파츠 역할" value={role} onChange={event => setRole(event.target.value)}>{Object.entries(roles).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
        <label>브러시<input type="range" aria-label="브러시 크기" min="0.005" max="0.12" step="0.005" value={radius} onChange={event => setRadius(Number(event.target.value))} /></label>
        <label><input type="checkbox" checked={erase} onChange={event => setErase(event.target.checked)} /> 지우기</label>
        <button onClick={() => viewer.current?.undoPaint()}>되돌리기</button><button onClick={() => viewer.current?.clearPaint()}>비우기</button>
        <span>{count}면 · 왼쪽 칠하기 / 오른쪽 회전</span>
      </> : <span>드래그 회전 · 원본 역할을 사용하고, 없는 영역은 자동 후보 분리</span>}
    </div>}
  </div>;
}
