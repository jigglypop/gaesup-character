import { useEffect, useState } from 'react';
import { standardApi, type StandardItem } from './standard-api';

type Run = (task: () => Promise<StandardItem>) => void;

export function GenerateDesign({ base, images, busy, run }: { base: StandardItem; images: StandardItem[]; busy: boolean; run: Run }) {
  const [name, setName] = useState('카디건 정면'), [objectKey, setObjectKey] = useState('cardigan'), [view, setView] = useState('front');
  const [description, setDescription] = useState('크림색 카디건, 짧고 둥근 SD 체형, 목과 어깨에 맞는 입구, 부드러운 니트 재질');
  const [reference, setReference] = useState<File>(), [prior, setPrior] = useState('');
  return <fieldset disabled={busy}><legend>2. 고정 몸 렌더로 파츠 시안 제작</legend>
    <p>Sunburst가 이 몸의 렌더를 기준으로 파츠 한 장을 만듭니다. 생성 후 착용 기준점을 실제로 측정·정렬해야 합니다.</p>
    <label>시안 이름<input value={name} onChange={e => setName(e.target.value)} /></label>
    <label>시안 물체 식별자<input value={objectKey} onChange={e => { setObjectKey(e.target.value); setPrior(''); }} /></label>
    <label>생성 시점<select value={view} onChange={e => setView(e.target.value)}><option value="front">정면</option><option value="side">측면</option><option value="back">후면</option></select></label>
    <label>디자인 지시<textarea rows={3} value={description} onChange={e => setDescription(e.target.value)} /></label>
    <label>원래 캐릭터·의상 참고 PNG (선택)<input type="file" accept="image/png" onChange={e => setReference(e.target.files?.[0])} /></label>
    <label>같은 파츠의 다른 시점 참조 (선택)<select value={prior} onChange={e => setPrior(e.target.value)}><option value="">추가 시점 없음</option>{images.filter(i => i.contract.object_key === objectKey).map(i => <option value={i.id} key={i.id}>{i.name}</option>)}</select></label>
    <button disabled={!name.trim() || !/^[a-zA-Z0-9_-]{1,80}$/.test(objectKey) || description.trim().length < 5} onClick={() => run(async () => {
      const referenceAsset = reference ? (await standardApi.upload(reference, 'png')).id : null;
      return standardApi.create('designs', { name, object_key: objectKey, base_id: base.id, base_sha256: base.model_sha256,
        view, description, reference_asset: referenceAsset, identity_image_id: prior || null, max_new_images: 1 });
    })}>Sunburst 시안 생성 · 유료 1회</button>
  </fieldset>;
}

type Point = [number, number];
type Anchor = { name: string; source: Point | null; target: Point | null };

function CoordinateInput({ label, point, change }: { label: string; point: Point | null; change: (point: Point | null) => void }) {
  const [text, setText] = useState(point?.join(',') || '');
  useEffect(() => { if (point) setText(point.join(',')); }, [point?.[0], point?.[1]]);
  return <input aria-label={label} value={text} placeholder="x,y" onChange={e => {
    setText(e.target.value); const p = e.target.value.split(',').map(Number);
    if (/^\d+(\.\d+)?,\s*\d+(\.\d+)?$/.test(e.target.value) && p.every(v => Number.isFinite(v) && v >= 0 && v < 2048)) change(p as Point);
    else change(null);
  }} />;
}

export function AlignDesign({ item, base, busy, run }: { item: StandardItem; base: StandardItem; busy: boolean; run: Run }) {
  const [anchors, setAnchors] = useState<Anchor[]>([{ name: 'neck', source: null, target: null }, { name: 'left', source: null, target: null }, { name: 'right', source: null, target: null }]);
  const [index, setIndex] = useState(0), [isolated, setIsolated] = useState(false), [same, setSame] = useState(false);
  const generated = item.artifacts.find(a => a.name === 'generated.png');
  const template = base.artifacts.find(a => a.name === `${item.contract.view}.png`);
  const complete = anchors.every(a => a.source && a.target);
  function setPoint(side: 'source' | 'target', point: Point | null, row = index) {
    setAnchors(previous => previous.map((a, i) => i === row ? { ...a, [side]: point } : a));
  }
  return <fieldset disabled={busy}><legend>생성 시안의 착용 기준점 정렬</legend>
    <p>기준점 이름을 선택한 다음 왼쪽 파츠와 오른쪽 몸에서 같은 위치를 클릭하세요. 목·어깨·허리 등 서로 떨어진 3점을 사용합니다. 시안 배율과 위치를 실제 좌표로 맞추며 비율이 어긋나면 수정이 필요하다고 표시합니다.</p>
    <div className="standard-anchor-choices">{anchors.map((a, i) => <button key={i} aria-pressed={index === i} onClick={() => setIndex(i)}>{i + 1}. {a.name}</button>)}</div>
    <div className="standard-alignment">{(['source', 'target'] as const).map(side => <div key={side}><strong>{side === 'source' ? '생성한 파츠' : '고정 몸 렌더'}</strong>
      <svg viewBox="0 0 2048 2048" role="img" aria-label={side === 'source' ? '생성 시안 기준점 선택' : '기준 몸 착용점 선택'} onClick={e => {
        if (busy) return; const box = e.currentTarget.getBoundingClientRect();
        setPoint(side, [Math.min(2047, Math.max(0, Math.round((e.clientX - box.left) * 2048 / box.width))), Math.min(2047, Math.max(0, Math.round((e.clientY - box.top) * 2048 / box.height)))]);
      }}>
        <image href={side === 'source' ? generated?.url : template?.url} width="2048" height="2048" />
        {anchors.map((a, i) => a[side] && <g key={i}><circle cx={a[side]![0]} cy={a[side]![1]} r="20" fill={i === index ? '#efb859' : '#5c8cff'} stroke="white" strokeWidth="6" /><text x={a[side]![0] + 28} y={a[side]![1]} fill="#294477" stroke="white" strokeWidth="1" fontSize="60">{i + 1}</text></g>)}
      </svg></div>)}</div>
    <table className="standard-anchor-table"><thead><tr><th>기준점</th><th>파츠 x,y</th><th>몸 x,y</th></tr></thead><tbody>{anchors.map((a, i) => <tr key={i}><td><input aria-label={`기준점 ${i + 1} 이름`} value={a.name} onChange={e => setAnchors(anchors.map((v, j) => i === j ? { ...v, name: e.target.value } : v))} /></td>{(['source', 'target'] as const).map(side => <td key={side}><CoordinateInput label={`${side} 기준점 ${i + 1}`} point={a[side]} change={point => setPoint(side, point, i)} /></td>)}</tr>)}</tbody></table>
    <label><input type="checkbox" checked={isolated} onChange={e => setIsolated(e.target.checked)} />배경·몸 없이 요청한 파츠 하나만 포함됨</label>
    <label><input type="checkbox" checked={same} onChange={e => setSame(e.target.checked)} />같은 디자인의 시점·착용 위치·입구를 확인함</label>
    <button disabled={!complete || !isolated || !same} onClick={() => run(() => standardApi.alignDesign(item.id, { source_sha256: item.result!.image_asset,
      anchors, max_error_px: 8, isolated_part_checked: true, same_object_checked: true }))}>측정점으로 정렬하고 생산 시안 저장</button>
  </fieldset>;
}
