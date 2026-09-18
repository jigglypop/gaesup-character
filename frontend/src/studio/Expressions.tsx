import { useCallback, useEffect, useState, type RefObject } from 'react';
import type { ModelViewer } from '../viewer';
import { defaultFaceLayout, expressionNames, type ExpressionMap, type ExpressionName, type FaceLayout } from '../texture-expressions';
import { studioApi, type Expression } from './api';
import { usePolling } from '../use-polling';

export function Expressions({ job, version, bodySha, viewer, ready }: {
  job:string;version:string;bodySha:string;viewer:RefObject<ModelViewer|null>;ready:boolean;
}) {
  const [name, setName] = useState<ExpressionName>('neutral');
  const [layout, setLayout] = useState(defaultFaceLayout), [maps, setMaps] = useState<ExpressionMap[]>([]);
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  const read = useCallback((signal:AbortSignal) => studioApi.expressions(job,version,signal),[job,version]);
  const saved = usePolling(read,15000);
  useEffect(() => { setName('neutral'); setMaps([]); },[ready]);
  async function apply(next:ExpressionName, values=layout) {
    if (!viewer.current) return;
    setBusy(true); setError('');
    try { setMaps(await viewer.current.expression(next,values)); setName(next); setLayout(values); }
    catch(e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  async function restore(record:Expression) {
    if (!viewer.current) return;
    setBusy(true);setError('');
    try {
      await viewer.current.savedExpression(record.materials.map(item => {
        const artifact=record.artifacts.find(a=>a.name===item.file);
        if (!artifact) throw new Error('표정 파일이 없습니다.');
        return {material:item.material,url:artifact.url,sha256:artifact.sha256};
      }));
      setName(record.name);setLayout(record.layout);setMaps([]);
    } catch(e) {setError((e as Error).message);} finally {setBusy(false);}
  }
  const adjust=(field:keyof FaceLayout,value:number)=>{setLayout(current=>({...current,[field]:value}));setMaps([]);};
  return <fieldset className="expression-controls" disabled={!ready||busy}><legend>표정</legend>
    <div className="meshy-buttons">{Object.entries(expressionNames).map(([key,label])=><button key={key} aria-pressed={name===key} onClick={()=>void apply(key as ExpressionName)}>{label}</button>)}</div>
    <details><summary>얼굴 위치</summary><div className="expression-layout">
      <label>눈 높이<input type="range" min=".3" max=".85" step=".005" value={layout.eye} onChange={e=>adjust('eye',Number(e.target.value))}/></label>
      <label>입 높이<input type="range" min=".5" max=".98" step=".005" value={layout.mouth} onChange={e=>adjust('mouth',Number(e.target.value))}/></label>
      <label>눈 간격<input type="range" min=".1" max=".35" step=".005" value={layout.spacing} onChange={e=>adjust('spacing',Number(e.target.value))}/></label>
      <label>크기<input type="range" min=".5" max="1.5" step=".05" value={layout.size} onChange={e=>adjust('size',Number(e.target.value))}/></label>
      <button onClick={()=>void apply(name)}>위치 적용</button>
    </div></details>
    <button disabled={!maps.length||name==='neutral'} onClick={()=>void(async()=>{
      if(name==='neutral')return;setBusy(true);setError('');
      try { const record=await studioApi.saveExpression(job,version,{body_sha256:bodySha,name,layout,maps});saved.setValue(current=>({items:[record,...(current?.items||[]).filter(r=>r.id!==record.id)]}));setMaps([]); }
      catch(e){setError((e as Error).message);}finally{setBusy(false);}
    })()}>표정 텍스쳐 저장</button>
    {(error||saved.error)&&<p role="alert">{error||saved.error}</p>}
    {saved.value?.items.map(record=><div className="meshy-buttons" key={record.id}><button onClick={()=>void restore(record)}>{expressionNames[record.name]}</button>{record.artifacts.filter(a=>a.name==='body.glb'||a.name==='manifest.json').map(a=><a key={a.name} href={a.url} download>{a.name==='body.glb'?'표정 GLB':'텍스쳐 정보'}</a>)}</div>)}
  </fieldset>;
}
