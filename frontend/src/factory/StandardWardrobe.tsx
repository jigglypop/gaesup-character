import { useEffect, useRef, useState } from 'react';
import { ModelViewer } from '../viewer';
import { outfitApi, type StandardItem } from './standard-api';

const slotNames: Record<string, string> = { top: '상의', bottom: '하의', hair: '헤어', hat: '모자', shoeLeft: '왼쪽 신발', shoeRight: '오른쪽 신발', accessory: '소품' };
const same = (a: string[], b: string[]) => a.length === b.length && a.every(id => b.includes(id));

export function StandardWardrobe({ base, parts, selected, onSelection }: {
  base: StandardItem; parts: StandardItem[]; selected: string[]; onSelection: (ids: string[]) => void;
}) {
  const mount = useRef<HTMLDivElement>(null), panel = useRef<HTMLElement>(null), viewer = useRef<ModelViewer | null>(null);
  const inputs = useRef({ parts, onSelection }); inputs.current = { parts, onSelection };
  const applied = useRef<string[]>([]), alive = useRef(true), saving = useRef(false);
  const [ready, setReady] = useState(false), [restored, setRestored] = useState(false), [loading, setLoading] = useState(false);
  const [clips, setClips] = useState<{ index: number; name: string }[]>([]), [motion, setMotion] = useState(-1);
  const [revision, setRevision] = useState('0'), [saved, setSaved] = useState<string[]>([]);
  const [pending, setPending] = useState(() => !!outfitApi.pending(base.id)), [busy, setBusy] = useState(false);
  const [modelError, setModelError] = useState(''), [wearError, setWearError] = useState(''), [saveError, setSaveError] = useState('');
  const [attempt, setAttempt] = useState(0);
  const url = base.artifacts.find(a => a.name === 'model.glb')?.url;
  const selectedKey = JSON.stringify(selected);
  const partsKey = JSON.stringify(parts.map(p => [p.id, p.contract.slot, p.artifacts.find(a => a.name === 'part.glb')]));

  async function restore() {
    setBusy(true); setSaveError('');
    try {
      const value = await outfitApi.get(base.id);
      if (!alive.current) return;
      if (value.base_sha256 !== base.model_sha256) throw new Error('저장한 옷장의 기준 몸 버전이 다릅니다.');
      const request = outfitApi.pending(base.id);
      const ids = request?.input.part_ids || value.part_ids;
      if (ids.some(id => !inputs.current.parts.some(part => part.id === id))) throw new Error('저장된 의상 파일을 목록에서 찾지 못했습니다. 연결 상태와 파츠 버전을 확인하세요.');
      setRevision(value.revision); setSaved(value.part_ids); setPending(!!request);
      inputs.current.onSelection(ids); setRestored(true);
    } catch (error) { if (alive.current) setSaveError((error as Error).message); }
    finally { if (alive.current) setBusy(false); }
  }

  useEffect(() => {
    alive.current = true; void restore();
    return () => { alive.current = false; };
  }, [base.id]);

  useEffect(() => {
    if (!url) { setModelError('기준 몸의 모델 파일이 없습니다.'); return; }
    let active = true; setReady(false); setModelError(''); setMotion(-1); applied.current = [];
    const instance = new ModelViewer(mount.current!, 'studio'); viewer.current = instance;
    void instance.load(url, { sha256: base.model_sha256, wardrobe: true }).then(value => {
      if (active) { setClips(value); setReady(true); }
    }).catch(error => { if (active) setModelError(error.message); });
    const timer = window.setInterval(() => {
      const diagnostic = instance.wardrobeDiagnostics();
      if (!diagnostic || !panel.current) return;
      panel.current.dataset.partIds = JSON.stringify(diagnostic.partIds);
      panel.current.dataset.sharedBones = String(diagnostic.shared);
      panel.current.dataset.boneCount = String(diagnostic.boneCount);
      panel.current.dataset.partSample = JSON.stringify(diagnostic.sample);
    }, 250);
    return () => { active = false; clearInterval(timer); instance.dispose(); viewer.current = null; };
  }, [url, base.model_sha256, attempt]);

  useEffect(() => {
    if (!ready || !restored || !viewer.current) return;
    let active = true; setLoading(true);
    void (async () => {
      const specs = selected.map(id => {
        const part = inputs.current.parts.find(p => p.id === id);
        const asset = part?.artifacts.find(a => a.name === 'part.glb');
        if (!part?.contract.slot || !asset?.sha256) throw new Error('피팅한 의상 파일과 버전 정보가 필요합니다.');
        return { id, slot: part.contract.slot, url: asset.url, sha256: asset.sha256 };
      });
      const equipped = await viewer.current!.wear(specs);
      if (active && equipped) applied.current = [...selected];
    })().catch(error => {
      if (active) { setWearError(error.message); inputs.current.onSelection([...applied.current]); }
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [selectedKey, partsKey, ready, restored]);

  async function save() {
    if (saving.current) return;
    saving.current = true; setBusy(true); setSaveError('');
    try {
      const result = await outfitApi.save(base.id, revision, { base_sha256: base.model_sha256!, part_ids: [...applied.current] });
      if (alive.current) { setRevision(result.revision); setSaved(result.part_ids); inputs.current.onSelection(result.part_ids); }
    } catch (error) { if (alive.current) setSaveError((error as Error).message); }
    finally {
      saving.current = false;
      if (alive.current) { setPending(!!outfitApi.pending(base.id)); setBusy(false); }
    }
  }

  const slots = Array.from(new Set(parts.map(p => p.contract.slot).filter((slot): slot is string => !!slot)));
  return <section className="standard-wardrobe" ref={panel} data-wardrobe-preview={base.id} data-wardrobe-ready={ready && restored ? base.id : ''}>
    <h2>옷 갈아입기</h2>
    <p>같은 기준 몸에 피팅한 의상을 골라 동작과 외형을 검수하세요. 선택한 옷은 즉시 바뀌며, 저장하면 다시 접속해도 유지됩니다.</p>
    <div className="wardrobe-scene" ref={mount} />
    {!ready && !modelError && <p role="status">공용 골격을 불러오는 중…</p>}
    {modelError && <p role="alert">{modelError} <button onClick={() => setAttempt(v => v + 1)}>몸 다시 불러오기</button></p>}
    <label>착용 동작<select aria-label="옷장 동작" disabled={!ready} value={motion} onChange={e => { const value = Number(e.target.value); setMotion(value); viewer.current?.play(value); }}>
      <option value={-1}>기본 자세</option>{clips.map(clip => <option key={clip.index} value={clip.index}>{clip.name}</option>)}
    </select></label>
    <fieldset disabled={!ready || !restored || busy || pending}><legend>착용할 의상</legend>
      {slots.length === 0 && <p>이 몸에 피팅한 의상이 준비되면 슬롯별로 선택할 수 있습니다.</p>}
      {slots.map(slot => <label key={slot}>{slotNames[slot] || slot}<select aria-label={`착용 ${slotNames[slot] || slot}`} value={selected.find(id => parts.some(p => p.id === id && p.contract.slot === slot)) || ''}
        onChange={e => { setWearError(''); const ids = selected.filter(id => parts.find(p => p.id === id)?.contract.slot !== slot); onSelection(e.target.value ? [...ids, e.target.value] : ids); }}>
        <option value="">벗기</option>{parts.filter(p => p.contract.slot === slot).map(part => <option key={part.id} value={part.id}>{part.name}</option>)}
      </select></label>)}
    </fieldset>
    {loading && <p role="status">의상을 불러오는 중…</p>}
    {wearError && <p role="alert">{wearError} 기존 착용을 유지했습니다.</p>}
    {saveError && <p role="alert">{saveError}</p>}
    {pending && <p role="status">착용 저장 응답을 확인하지 못했습니다. 같은 요청으로 저장 결과를 복구할 수 있습니다.</p>}
    <button disabled={busy || loading || !ready || !restored || !same(selected, applied.current) || (!pending && same(selected, saved))} onClick={() => void save()}>{pending ? '착용 저장 결과 복구' : '현재 착용 저장'}</button>
    <button disabled={busy || pending} onClick={() => void restore()}>저장한 착용 다시 불러오기</button>
    {restored && !pending && same(selected, saved) && <p role="status">저장한 착용과 같습니다.</p>}
  </section>;
}
