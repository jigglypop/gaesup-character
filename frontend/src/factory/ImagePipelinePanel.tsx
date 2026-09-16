import { useCallback, useEffect, useRef, useState } from 'react';
import { request, ApiError } from '../api';
import { factoryApi, type FactoryCapabilities, type FactoryJob } from './api';
import { layerBitmap, type Blueprint } from './image-layers';

const characterSlots=['body','hairBack','hairFront','hat','top','bottom','shoes'];
const names: Record<string,string> = {body:'대머리 기본몸 · 얼굴 포함',face:'얼굴',hairBack:'뒷머리 · 숨은 두피 포함 후보',hairFront:'앞머리 · 얼굴 둘레',hat:'모자',top:'상의',bottom:'하의',shoes:'신발 한 쌍',weapon:'무기',shield:'방패',back:'등 장비',faceAccessory:'얼굴 장식',neckAccessory:'목 장식'};
const statuses: Record<string,string> = {pending:'대기',received:'이미지 수신 · 저장 복구 가능',submitting:'응답 확인 중',succeeded:'이미지 완료',rejected:'요청 거절',PENDING:'생성 대기',IN_PROGRESS:'생성 중',SUCCEEDED:'다운로드 중',ready:'3D 완료',FAILED:'생성 실패',CANCELED:'취소됨'};

export function ImagePipelinePanel({blueprint,onBlueprint,dirty}:{blueprint:Blueprint;onBlueprint:(b:Blueprint)=>void;dirty:boolean}) {
  const [capabilities,setCapabilities]=useState<FactoryCapabilities>(),[jobs,setJobs]=useState<FactoryJob[]>([]);
  const [error,setError]=useState(''),[connection,setConnection]=useState(''),[busy,setBusy]=useState(false),[mode,setMode]=useState<'generate'|'prepared'>('generate');
  const [productionMode,setProductionMode]=useState<'character_parts'|'legacy'>('character_parts');
  const [slots,setSlots]=useState(['body']),[chosen,setChosen]=useState(''),[taskId,setTaskId]=useState('');
  const [reuseParts,setReuseParts]=useState(false),[reuseJobId,setReuseJobId]=useState('');
  const [bodyPurpose,setBodyPurpose]=useState<'whole_character'|'wardrobe_base'>('wardrobe_base');
  const [motionDefaults,setMotionDefaults]=useState<Record<string,number>>({});
  const lock=useRef(false);
  const pending=factoryApi.pendingImage(blueprint.character_id);
  const requestedMode=pending?(pending.input.production_mode||'legacy'):productionMode;
  const selectedSlots=pending?.input.slots||(requestedMode==='character_parts'?characterSlots:slots);
  const imageMode=requestedMode==='character_parts'?'generate':mode;
  const action=capabilities?.next_actions.find(a=>a.id===(imageMode==='generate'?'produce_images':'produce_prepared'));
  const job=jobs.find(j=>j.id===chosen)||jobs[0];
  const reusable=jobs.filter(j=>j.source_sha256===blueprint.source_sha256&&j.parts?.some(p=>p.slot!=='body'&&p.image_status==='succeeded'&&p.model_status==='ready'));
  const reuseSource=pending
    ? jobs.find(j=>j.id===pending.input.reuse_job_id)
    : reusable.find(j=>j.id===reuseJobId)||reusable[0];
  const reusableSlots=new Set(reuseSource?.parts?.filter(p=>p.slot!=='body'&&p.image_status==='succeeded'&&p.model_status==='ready').map(p=>p.slot)||[]);
  const reuseEnabled=pending?!!pending.input.reuse_job_id:reuseParts;
  const reuseCount=requestedMode==='character_parts'&&reuseEnabled?characterSlots.filter(slot=>slot!=='body'&&reusableSlots.has(slot)).length:0;
  const active=jobs.some(j=>['pipeline_queued','pipeline_running','accepted','running'].includes(j.status));
  const refresh=useCallback(async()=>{
    try {
      const [list,config,defaults]=await Promise.all([factoryApi.list(),factoryApi.capabilities(),factoryApi.motionDefaults()]);
      const related=list.jobs.filter(j=>j.character_id===blueprint.character_id&&j.input_kind==='image').sort((a,b)=>b.created_at.localeCompare(a.created_at));
      setJobs(related);setReuseJobId(current=>current||related.find(j=>j.source_sha256===blueprint.source_sha256&&j.parts?.some(p=>p.slot!=='body'&&p.image_status==='succeeded'&&p.model_status==='ready'))?.id||'');
      setCapabilities(config);setMotionDefaults(defaults.selections);setConnection('');
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
      const input=pending?.input||(productionMode==='character_parts'
        ? {character_id:saved.character_id,source_sha256:saved.source_sha256!,blueprint_revision:saved.revision,image_mode:'generate' as const,production_mode:'character_parts' as const,slots:characterSlots,reuse_job_id:reuseParts&&reuseSource?reuseSource.id:undefined,rig_with_meshy:true,body_purpose:'wardrobe_base' as const,motion_actions:motionDefaults}
        : {character_id:saved.character_id,source_sha256:saved.source_sha256!,blueprint_revision:saved.revision,image_mode:mode,production_mode:'legacy' as const,slots,rig_with_meshy:slots.includes('body'),body_purpose:slots.includes('body')?bodyPurpose:'whole_character' as const,motion_actions:slots.includes('body')?motionDefaults:{}});
      const result=await factoryApi.produceImage(input);
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
  const expectedTasks=selectedSlots.length-reuseCount;
  const characterJob=job?.production_mode==='character_parts'||(job?.parts?.some(p=>p.slot==='body')&&job.parts.length>1);
  const artifactFor=(slot:string)=>job?.artifacts.find(a=>a.name===`generated-${slot}.glb`);
  const unsupported=requestedMode==='character_parts'&&!!capabilities?.slots&&characterSlots.some(slot=>!capabilities.slots.includes(slot));
  return <section className="image-production" aria-label="캐릭터 파츠 생산">
    <div className="image-production-title"><div><span className="image-kicker">ONE CHARACTER IMAGE → 7 NATIVE PARTS</span><h2>한 캐릭터 파츠 전체 분리</h2><p>원본 캐릭터 디자인을 대머리 기본몸·앞머리·뒷머리·모자·상의·하의·신발로 나눠 각각 이미지와 3D를 만듭니다.</p></div><span className="image-production-config">{capabilities?.image_model||'GPT Image 2.5'} {capabilities?.image_configured?'연결 설정됨':'설정 필요'} · Meshy {capabilities?.meshy_configured?'연결 설정됨':'설정 필요'} · Blender {capabilities?.blender_available?'준비됨':'설치 필요'}</span></div>
    <div className="image-production-options"><label>생산 방식<select aria-label="생산 방식" value={requestedMode} disabled={busy||active||!!pending} onChange={e=>setProductionMode(e.target.value as typeof productionMode)}><option value="character_parts">기본 · 캐릭터 7파트 한 세트</option><option value="legacy">고급 · 기존 단일 몸/선택 파츠</option></select></label></div>
    {requestedMode==='character_parts'?<>
      <div className="image-production-slots" aria-label="기본 7파트">{characterSlots.map(slot=><label key={slot}><input type="checkbox" checked readOnly disabled/>{names[slot]}</label>)}</div>
      <p className="image-notice">기본몸은 대머리 머리·원본 얼굴·귀·목·팔다리·손발을 포함합니다. 원본에 가려진 두피·몸·의상 안쪽은 생성으로 보완한 <b>검수 후보</b>이며 실제 원본 형태로 확정하지 않습니다.</p>
      <fieldset disabled={busy||active||!!pending}><legend>기존 파츠 사용</legend><label><input type="radio" name="reuse-parts" checked={!reuseEnabled} onChange={()=>setReuseParts(false)}/>7파트 모두 새로 생성 · 기본</label><label><input type="radio" name="reuse-parts" checked={reuseEnabled} disabled={!reusable.length} onChange={()=>setReuseParts(true)}/>검증 가능한 기존 분리 파츠 재사용</label>{reuseEnabled&&reuseSource&&<label>재사용 후보<select aria-label="기존 분리 파츠 재사용" value={reuseSource.id} onChange={e=>setReuseJobId(e.target.value)}>{reusable.map(candidate=><option key={candidate.id} value={candidate.id}>{new Date(candidate.created_at).toLocaleString()} · {candidate.parts?.filter(p=>p.slot!=='body'&&p.image_status==='succeeded'&&p.model_status==='ready').length||0}/6 기술 완료 · 외형 검수 후보</option>)}</select></label>}<small>재사용은 품질 승인이 아닙니다. 서버가 같은 원본과 각 이미지·GLB 해시를 다시 확인하며, 대머리 기본몸은 항상 새로 생성합니다.</small></fieldset>
    </>:<>
      <div className="image-production-options"><label>이미지 입력<select aria-label="생산 이미지 입력" value={mode} disabled={busy||active} onChange={e=>setMode(e.target.value as typeof mode)}><option value="generate">원본을 참고해 선택 대상 생성</option><option value="prepared">현재 편집한 PNG 사용</option></select></label><div className="image-production-slots">{Object.entries(names).map(([slot,name])=><label key={slot}><input type="checkbox" checked={slots.includes(slot)} disabled={busy||active||!!(capabilities?.slots&&!capabilities.slots.includes(slot))} onChange={e=>setSlots(s=>e.target.checked?(slot==='body'?['body']:[...s.filter(v=>v!=='body'),slot]):s.filter(v=>v!==slot))}/>{name}</label>)}</div></div>
      {slots.includes('body')&&<label>전신의 용도<select aria-label="전신의 용도" value={bodyPurpose} disabled={busy||active||!!pending} onChange={e=>setBodyPurpose(e.target.value as typeof bodyPurpose)}><option value="wardrobe_base">대머리 기본몸</option><option value="whole_character">반팔·반바지를 입은 완성 전신</option></select><small>고급 legacy 경로입니다. 몸과 착용 파츠를 한 세트로 함께 만들려면 기본 7파트 생산을 사용하세요.</small></label>}
    </>}
    <div className="image-production-start"><p><b>{blueprint.character_id}</b> · 신규 유료 예상 이미지 {imageMode==='generate'?expectedTasks:0}회 + Meshy {expectedTasks}회{selectedSlots.includes('body')?` + 실제 Meshy 리깅 1회 + 저장 동작 최대 ${new Set(Object.values(motionDefaults)).size}회`:''}<br/><small>{requestedMode==='character_parts'?`신규 기본몸 1개와 ${reuseCount?`재사용 ${reuseCount}개·신규 ${6-reuseCount}개`: '신규 착용 파츠 6개'}를 요청합니다.`:'선택한 legacy 대상을 생산합니다.'} 요청 당시 원본 SHA·동작 ID·재사용 job을 고정하며 결과는 모두 외형 검수가 필요합니다.</small></p><button className="image-primary" disabled={busy||(!pending&&(active||!action?.enabled||unsupported||!blueprint.source_sha256||!selectedSlots.length))} onClick={()=>void produce()}>{busy?'요청 저장 중…':pending?'같은 생산 요청 복구':active?'캐릭터 파츠 생산 진행 중':requestedMode==='character_parts'?'한 캐릭터 파츠 전체 분리':'고급 생산 실행'}</button></div>
    {unsupported&&<p role="alert" className="image-error">백엔드가 7파트 생산 계약을 아직 지원하지 않습니다. 서버 버전을 확인하세요.</p>}
    {action?.reason&&<p className="image-notice">{action.reason}</p>}
    {(error||connection)&&<p role="alert" className="image-error">{error||connection}</p>}
    {job&&<div className="image-production-job"><div className="image-production-title"><select aria-label="이미지 생산 버전" value={job.id} onChange={e=>setChosen(e.target.value)}>{jobs.map(j=><option key={j.id} value={j.id}>{new Date(j.created_at).toLocaleString()} · {j.id.slice(0,8)}</option>)}</select><strong role="status">{job.status==='review_required'?'생성 결과 · 검수 대기':job.progress.message}</strong></div>
      {characterJob&&<p>원본 이미지와 아래 7개 결과를 비교해 얼굴·실루엣·앞/뒷머리 중복·의상 절개·가려졌던 면의 생성 보완을 각각 검수하세요.</p>}
      <div className="image-production-parts">{job.parts?.map(part=>{const model=artifactFor(part.slot);return <div key={part.slot}>{part.image_asset&&<img src={`/api/avatar-blueprints/assets/${part.image_asset}`} alt={`${names[part.slot]||part.slot} 생성 이미지`}/>}<b>{names[part.slot]||part.slot}</b><span>이미지 · {statuses[part.image_status]||part.image_status}</span><span>3D · {statuses[part.model_status]||part.model_status} {part.progress?`${part.progress}%`:''}</span>{part.slot==='body'&&<small>대머리 기본몸 · 얼굴 포함 · Meshy 원본 리그 대상</small>}{part.task_id&&<small title={part.task_id}>Meshy {part.task_id.slice(0,8)}</small>}<span>{part.image_asset&&<a href={`/api/avatar-blueprints/assets/${part.image_asset}`} download>PNG 받기</a>}{model&&<> · <a href={model.url} download>GLB 받기</a></>}</span></div>;})}</div>
      {job.error&&<p role="alert" className="image-error">{job.error}</p>}
      {job.parts?.filter(p=>p.model_status==='submission_uncertain'&&!p.task_id).map(p=><form key={p.slot} onSubmit={e=>{e.preventDefault();void recover(p.slot);}}><label>{names[p.slot]} 기존 Meshy 작업 ID <input aria-label={`${names[p.slot]} Meshy 작업 ID`} required pattern="[a-zA-Z0-9_-]+" value={taskId} onChange={e=>setTaskId(e.target.value)}/></label><button disabled={busy}>작업 ID 조회·복구</button></form>)}
      <div className="image-production-actions">{job.next_actions?.find(a=>a.id==='resume')&&<button disabled={busy||!job.next_actions.find(a=>a.id==='resume')?.enabled} onClick={()=>void resume()}>기존 작업 이어가기</button>}{job.parts?.some(p=>p.image_asset)&&<button onClick={()=>onBlueprint({...blueprint,layers:blueprint.layers.map(l=>{const p=job.parts?.find(p=>p.slot===l.slot);return p?.image_asset?{...l,asset:p.image_asset,crop:[0,0,1,1],background:'border-gray',status:'design_candidate'}:l;})})}>세트 결과를 비교 화면에 가져오기</button>}{(job.outfit||job.artifacts.some(a=>a.name==='generated-body.glb'))&&<a className="image-primary" href={`/avatar.html?stage=glb&character=${job.character_id}&job=${job.id}&tab=result`}>{characterJob?'기본몸 리그·6개 동작·파츠 검수':'3D 결과 검수'}</a>}{job.artifacts.filter(a=>!characterJob&&['character.glb','master.blend'].includes(a.name)).map(a=><a key={a.name} href={a.url} download>{a.name}</a>)}</div>
      {job.next_actions?.find(a=>a.id==='resume')?.reason&&<p>{job.next_actions.find(a=>a.id==='resume')?.reason}</p>}
    </div>}
  </section>;
}
