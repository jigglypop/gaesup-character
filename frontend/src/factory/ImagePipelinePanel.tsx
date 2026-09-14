import { useCallback, useEffect, useRef, useState } from 'react';
import { request, ApiError } from '../api';
import { factoryApi, type FactoryCapabilities, type FactoryJob } from './api';
import { layerBitmap, type Blueprint } from './image-layers';

const names: Record<string,string> = {face:'얼굴',hairBack:'뒷머리',hairFront:'앞머리',hat:'모자',top:'상의',bottom:'하의',shoes:'신발'};
const statuses: Record<string,string> = {pending:'대기',submitting:'제출 중',succeeded:'이미지 완료',rejected:'요청 거절',PENDING:'생성 대기',IN_PROGRESS:'생성 중',SUCCEEDED:'다운로드 중',ready:'3D 완료',FAILED:'생성 실패',CANCELED:'취소됨'};

export function ImagePipelinePanel({blueprint,onBlueprint,dirty}:{blueprint:Blueprint;onBlueprint:(b:Blueprint)=>void;dirty:boolean}) {
  const [capabilities,setCapabilities]=useState<FactoryCapabilities>(),[jobs,setJobs]=useState<FactoryJob[]>([]);
  const [error,setError]=useState(''),[connection,setConnection]=useState(''),[busy,setBusy]=useState(false),[mode,setMode]=useState<'generate'|'prepared'>('generate');
  const [slots,setSlots]=useState(Object.keys(names)),[chosen,setChosen]=useState(''),[taskId,setTaskId]=useState('');
  const lock=useRef(false);
  const pending=factoryApi.pendingImage(blueprint.character_id);
  const action=capabilities?.next_actions.find(a=>a.id===(mode==='generate'?'produce_images':'produce_prepared'));
  const job=jobs.find(j=>j.id===chosen)||jobs[0];
  const active=jobs.some(j=>['pipeline_queued','pipeline_running','accepted','running'].includes(j.status));
  const refresh=useCallback(async()=>{
    try {
      const [list,config]=await Promise.all([factoryApi.list(),factoryApi.capabilities()]);
      setJobs(list.jobs.filter(j=>j.character_id===blueprint.character_id&&j.input_kind==='image').sort((a,b)=>b.created_at.localeCompare(a.created_at)));
      setCapabilities(config);setConnection('');
    }catch(e){setConnection((e as Error).message);}
  },[blueprint.character_id]);
  useEffect(()=>{let active=true;const reload=()=>{if(active&&!document.hidden)void refresh();};reload();const timer=setInterval(reload,3000);window.addEventListener('online',reload);return()=>{active=false;clearInterval(timer);window.removeEventListener('online',reload);};},[refresh]);
  async function produce() {
    if(lock.current||!blueprint.source_sha256)return;lock.current=true;setBusy(true);setError('');
    try {
      let saved=blueprint;
      if(!pending) {
        const layers=await Promise.all(blueprint.layers.map(async layer=>{
          if(mode!=='prepared'||!slots.includes(layer.slot))return layer;
          if(!layer.asset)throw new Error(`${layer.label}: 개별 파츠 이미지가 필요합니다.`);
          const canvas=await layerBitmap(layer);
          const blob=await new Promise<Blob>((resolve,reject)=>canvas.toBlob(b=>b?resolve(b):reject(new Error('PNG 내보내기 실패')),'image/png'));
          const asset=await request<{id:string}>('/api/avatar-blueprints/assets',{method:'POST',headers:{'Content-Type':'image/png'},body:blob});
          return {...layer,asset:asset.id,crop:[0,0,1,1] as [number,number,number,number],background:'alpha' as const};
        }));
        if(dirty||mode==='prepared') {
          const key=`gaesup.blueprint.pending:${blueprint.character_id}`;
          const receipt=JSON.parse(sessionStorage.getItem(key)||'null')||{key:crypto.randomUUID(),revision:blueprint.revision,layers};
          sessionStorage.setItem(key,JSON.stringify(receipt));
          try {
            saved=await request<Blueprint>(`/api/avatar-blueprints/${blueprint.character_id}`,{method:'PUT',headers:{'Content-Type':'application/json','If-Match':receipt.revision,'Idempotency-Key':receipt.key},body:JSON.stringify({layers:receipt.layers})});
            sessionStorage.removeItem(key);
          }catch(e){if(e instanceof ApiError&&e.status>=400&&e.status<500)sessionStorage.removeItem(key);throw e;}
          onBlueprint(saved);
        }
      }
      const result=await factoryApi.produceImage(pending?.input||{character_id:saved.character_id,source_sha256:saved.source_sha256!,blueprint_revision:saved.revision,image_mode:mode,slots});
      setChosen(result.id);await refresh();
    }catch(e){setError((e as Error).message);}finally{lock.current=false;setBusy(false);}
  }
  async function resume() {
    if(!job||lock.current)return;lock.current=true;setBusy(true);
    try{await factoryApi.resume(job.id);await refresh();}catch(e){setError((e as Error).message);}finally{lock.current=false;setBusy(false);}
  }
  async function recover(slot:string) {
    if(!job||lock.current)return;lock.current=true;setBusy(true);
    try{await factoryApi.recoverPart(job.id,slot,taskId.trim());setTaskId('');await refresh();}catch(e){setError((e as Error).message);}finally{lock.current=false;setBusy(false);}
  }
  return <section className="image-production" aria-label="전체 자동 생산">
    <div className="image-production-title"><div><span className="image-kicker">ONE IMAGE → MODULAR AVATAR</span><h2>이미지부터 공통 리그까지</h2><p>파츠 이미지 → 개별 Meshy 7 생성 → 공통 몸에 맞춤 → 23본 리깅 → GLB·Blender</p></div><span className="image-production-config">Gemini {capabilities?.image_configured?'연결 설정됨':'설정 필요'} · Meshy {capabilities?.meshy_configured?'연결 설정됨':'설정 필요'} · Blender {capabilities?.blender_available?'준비됨':'설치 필요'}</span></div>
    <div className="image-production-options"><label>이미지 입력<select aria-label="생산 이미지 입력" value={mode} disabled={busy||active} onChange={e=>setMode(e.target.value as typeof mode)}><option value="generate">원본에서 파츠 분리·숨은 형태 자동 생성</option><option value="prepared">현재 편집한 파츠 PNG 사용</option></select></label><div className="image-production-slots">{Object.entries(names).map(([slot,name])=><label key={slot}><input type="checkbox" checked={slots.includes(slot)} disabled={busy||active} onChange={e=>setSlots(s=>e.target.checked?[...s,slot]:s.filter(v=>v!==slot))}/>{name}</label>)}</div></div>
    <div className="image-production-start"><p><b>{blueprint.character_id}</b> · 유료 이미지 최대 {mode==='generate'?slots.length:0}회 + Meshy 최대 {slots.length}회<br/><small>공통 몸·리깅·조립은 로컬 처리합니다. 결과는 외형·변형 검수가 필요한 새 버전으로 저장됩니다.</small></p><button className="image-primary" disabled={busy||(!pending&&(active||!action?.enabled||!blueprint.source_sha256||!slots.length))} onClick={()=>void produce()}>{busy?'요청 저장 중…':pending?'같은 생산 요청 복구':active?'전체 파이프라인 진행 중':'전체 자동 생산'}</button></div>
    {action?.reason&&<p className="image-notice">{action.reason}</p>}
    {(error||connection)&&<p role="alert" className="image-error">{error||connection}</p>}
    {job&&<div className="image-production-job"><div className="image-production-title"><select aria-label="이미지 생산 버전" value={job.id} onChange={e=>setChosen(e.target.value)}>{jobs.map(j=><option key={j.id} value={j.id}>{new Date(j.created_at).toLocaleString()} · {j.id.slice(0,8)}</option>)}</select><strong role="status">{job.status==='review_required'?'조립 완료 · 검수 대기':job.progress.message}</strong></div>
      <div className="image-production-parts">{job.parts?.map(part=><div key={part.slot}>{part.image_asset&&<img src={`/api/avatar-blueprints/assets/${part.image_asset}`} alt={`${names[part.slot]} 생성 이미지`}/>}<b>{names[part.slot]}</b><span>{statuses[part.image_status]||part.image_status}</span><span>{statuses[part.model_status]||part.model_status} {part.progress?`${part.progress}%`:''}</span>{part.task_id&&<small title={part.task_id}>Meshy {part.task_id.slice(0,8)}</small>}</div>)}</div>
      {job.error&&<p role="alert" className="image-error">{job.error}</p>}
      {job.parts?.filter(p=>p.model_status==='submission_uncertain'&&!p.task_id).map(p=><form key={p.slot} onSubmit={e=>{e.preventDefault();void recover(p.slot);}}><label>{names[p.slot]} 기존 Meshy 작업 ID <input aria-label={`${names[p.slot]} Meshy 작업 ID`} required pattern="[a-zA-Z0-9_-]+" value={taskId} onChange={e=>setTaskId(e.target.value)}/></label><button disabled={busy}>작업 ID 조회·복구</button></form>)}
      <div className="image-production-actions">{job.next_actions?.find(a=>a.id==='resume')&&<button disabled={busy||!job.next_actions.find(a=>a.id==='resume')?.enabled} onClick={()=>void resume()}>기존 작업 이어가기</button>}{job.parts?.some(p=>p.image_asset)&&<button onClick={()=>onBlueprint({...blueprint,layers:blueprint.layers.map(l=>{const p=job.parts?.find(p=>p.slot===l.slot);return p?.image_asset?{...l,asset:p.image_asset,crop:[0,0,1,1],background:'border-gray',status:'design_candidate'}:l;})})}>생성 이미지를 편집 화면에 가져오기</button>}{job.outfit&&<a className="image-primary" href={`/avatar.html?stage=glb&character=${job.character_id}&job=${job.id}&tab=result`}>조립 3D · 동작 · 파츠 교체 확인</a>}{job.artifacts.filter(a=>['character.glb','master.blend'].includes(a.name)).map(a=><a key={a.name} href={a.url} download>{a.name}</a>)}</div>
      {job.next_actions?.find(a=>a.id==='resume')?.reason&&<p>{job.next_actions.find(a=>a.id==='resume')?.reason}</p>}
    </div>}
  </section>;
}
