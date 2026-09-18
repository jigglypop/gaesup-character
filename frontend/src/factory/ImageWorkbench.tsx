import { useCallback, useEffect, useRef, useState } from 'react';
import { api, request, ApiError } from '../api';
import { useLiveCharacters } from '../studio/characters';
import { StudioIcon } from '../studio/icons';
import { layerBitmap, downloadCanvas, type Blueprint, type ImageLayer } from './image-layers';
import './images.css';
import { ImagePipelinePanel } from './ImagePipelinePanel';

function LayerThumb({ layer }: { layer: ImageLayer }) {
  const [url,setUrl]=useState('');
  useEffect(()=>{let active=true;if(layer.asset)void layerBitmap(layer).then(canvas=>{if(active)setUrl(canvas.toDataURL());}).catch(()=>setUrl(''));else setUrl('');return()=>{active=false;};},[layer.asset,layer.crop,layer.background]);
  return url?<img src={url} alt=""/>:<StudioIcon name="layers"/>;
}

export function ImageWorkbench() {
  const live=useLiveCharacters();
  const [sourceId,setSourceId]=useState(new URLSearchParams(location.search).get('character')||'');
  const source=live.characters.find(c=>c.id===sourceId)||live.characters[0];
  const [blueprint,setBlueprint]=useState<Blueprint>(),[selected,setSelected]=useState('top');
  const [error,setError]=useState(''),[notice,setNotice]=useState(''),[busy,setBusy]=useState(false),[dirty,setDirty]=useState(false);
  const [guides,setGuides]=useState(true),[exploded,setExploded]=useState(false),[ghost,setGhost]=useState(false);
  const canvas=useRef<HTMLCanvasElement>(null),busyRef=useRef(false),generation=useRef(0),edits=useRef(0);
  const layer=blueprint?.layers.find(l=>l.slot===selected);
  const pendingKey=source?`gaesup.blueprint.pending:${source.id}`:'';
  const load=useCallback(async()=>{
    if(!source)return;
    const token=++generation.current;
    try{
      const value=await request<Blueprint>(`/api/avatar-blueprints/${source.id}`);
      if(token!==generation.current)return;
      const pending=sessionStorage.getItem(`gaesup.blueprint.pending:${source.id}`);
      setBlueprint(pending?{...value,layers:JSON.parse(pending).layers}:value);setDirty(!!pending);setError('');
      setNotice(pending?'응답이 확인되지 않은 저장이 있습니다. 설계 저장으로 같은 요청을 복구합니다.':'');
    }catch(error){if(token===generation.current)setError((error as Error).message);}
  },[source?.id]);
  useEffect(()=>{setBlueprint(undefined);setDirty(false);void load();return()=>{generation.current++;};},[load]);
  useEffect(()=>{
    const reconnect=()=>{if(!dirty)void load();};window.addEventListener('online',reconnect);return()=>window.removeEventListener('online',reconnect);
  },[load,dirty]);
  useEffect(()=>{
    if(!blueprint||!canvas.current)return;let active=true;
    const layers=blueprint.layers.filter(l=>l.asset&&l.visible).sort((a,b)=>a.order-b.order);
    void Promise.all(layers.map(async l=>({layer:l,bitmap:await layerBitmap(l)}))).then(items=>{
      if(!active||!canvas.current)return;
      const ctx=canvas.current.getContext('2d')!;ctx.clearRect(0,0,512,512);
      for(const {layer,bitmap} of items){ctx.globalAlpha=layer.opacity*(ghost&&layer.slot!==selected? .38:1);ctx.drawImage(bitmap,...layer.placement);}
      ctx.globalAlpha=1;canvas.current.dataset.layers=String(items.length);
    }).catch(error=>{if(active)setError(error.message);});return()=>{active=false;};
  },[blueprint,ghost,selected]);
  function update(values:Partial<ImageLayer>,slot=selected){edits.current++;setBlueprint(b=>b?{...b,layers:b.layers.map(l=>l.slot===slot?{...l,...values}:l)}:b);setDirty(true);setNotice('');}
  function selectSource(id:string){generation.current++;setSourceId(id);const url=new URL(location.href);url.searchParams.set('character',id);history.replaceState(null,'',url);}
  async function save(){
    if(!source||!blueprint||busyRef.current)return;busyRef.current=true;setBusy(true);setError('');
    const pending=JSON.parse(sessionStorage.getItem(pendingKey)||'null')||{key:crypto.randomUUID(),revision:blueprint.revision,layers:blueprint.layers};
    const token=generation.current,edit=edits.current,matched=JSON.stringify(blueprint.layers)===JSON.stringify(pending.layers);
    sessionStorage.setItem(pendingKey,JSON.stringify(pending));
    try{
      const result=await request<Blueprint>(`/api/avatar-blueprints/${source.id}`,{method:'PUT',headers:{'Content-Type':'application/json','If-Match':pending.revision,'Idempotency-Key':pending.key},body:JSON.stringify({layers:pending.layers})});
      sessionStorage.removeItem(pendingKey);
      if(token!==generation.current)return;
      const changed=edit!==edits.current||!matched;
      setBlueprint(current=>changed&&current?{...result,layers:current.layers}:result);setDirty(changed);
      setNotice(changed?'이전 저장을 확인했습니다. 추가 편집은 저장해 주세요.':'이미지 파츠 설계를 저장했습니다.');
    }
    catch(error){if(error instanceof ApiError&&error.status>=400&&error.status<500)sessionStorage.removeItem(pendingKey);if(token===generation.current)setError((error as Error).message);}
    finally{busyRef.current=false;setBusy(false);}
  }
  async function upload(file:File|undefined,reference=false){
    if(!file||busyRef.current)return;busyRef.current=true;setBusy(true);setError('');
    try{
      if(reference){const c=await api.create(file.name.replace(/\.[^.]+$/,''),null);await api.upload(c,file,'image');await live.refresh();selectSource(c.id);}
      else{const image=await request<{id:string;alpha:boolean}>('/api/avatar-blueprints/assets',{method:'POST',headers:{'Content-Type':'image/png'},body:file});update({asset:image.id,crop:[0,0,1,1],background:image.alpha?'alpha':'border-gray',status:'design_candidate'});}
    }catch(error){setError((error as Error).message);}finally{busyRef.current=false;setBusy(false);}
  }
  return <div className="image-factory">
    <header className="image-header"><a href="/avatar.html"><StudioIcon name="cube" size={25}/><b>gaesup</b><span>AVATAR FACTORY</span></a><nav><a href="/avatar.html?stage=standard">고정 몸 · 공용 골격</a><strong>01 이미지 파츠 설계</strong><a href={`/avatar.html?stage=glb${source?`&character=${source.id}`:''}`}>02 기존 GLB 변환</a><a href="/avatar.html?view=wardrobe">런타임 옷장</a></nav></header>
    <aside className="image-sources"><span className="image-kicker">SOURCE LIBRARY</span><h2>캐릭터 이미지부터 시작</h2><p>특정 캐릭터를 고정하지 않고<br/>선택한 원본 한 장을 6파트 세트로 분리합니다.</p><label className="image-upload">＋ 캐릭터 이미지 가져오기<input type="file" accept="image/png,image/jpeg" disabled={busy} aria-label="캐릭터 이미지 가져오기" onChange={e=>{void upload(e.target.files?.[0],true);e.target.value='';}}/></label>{live.characters.map(c=>{const ref=c.artifacts.find(a=>a.id==='reference');return <button className={`image-source ${source?.id===c.id?'selected':''}`} key={c.id} onClick={()=>selectSource(c.id)}>{ref?<img src={ref.url} alt=""/>:<StudioIcon name="cube"/>}<span>{c.name}<small>{ref?'분리할 원본 이미지':'GLB 입력'}</small></span></button>;})}<div className="image-common"><span className="image-kicker">ONE CHARACTER SET</span><h3>대머리 기본몸 + 착용 파츠 5개</h3><p>얼굴 포함 기본몸, 머리카락,<br/>모자, 상의, 하의, 신발을 같은 원본에서 만듭니다.<br/>가려진 면은 생성 보완 후 별도 검수합니다.</p></div></aside>
    <main className="image-main"><div className="image-heading"><div><span className="image-kicker">IMAGE → PARTS → OVERLAY → 3D</span><h1>{source?.name||'캐릭터'} 파츠 설계</h1><p>가려진 부분까지 완성하고, 이미지 조합을 맞춘 뒤 각 파츠를 3D로 만듭니다.</p></div><button className="image-primary" disabled={!blueprint||busy} onClick={()=>void save()}>{busy?'저장 중…':dirty?'설계 저장 *':'설계 저장'}</button></div>
      {(error||live.failure)&&<div role="alert" className="image-error">{error||live.failure}<button onClick={()=>{void load();void live.refresh();}}>다시 불러오기</button></div>}{notice&&<p role="status" className="image-notice">{notice}</p>}
      <div className="image-workspace"><section className="image-preview"><div className="image-preview-bar"><button aria-pressed={!exploded} onClick={()=>setExploded(false)}>겹쳐 보기</button><button aria-pressed={exploded} onClick={()=>setExploded(true)}>파츠 펼쳐 보기</button><label><input type="checkbox" checked={guides} onChange={e=>setGuides(e.target.checked)}/> 연결점</label><label><input type="checkbox" checked={ghost} onChange={e=>setGhost(e.target.checked)}/> 선택 파츠 강조</label></div>
        <div className={`image-canvas-stage ${exploded?'show-exploded':''}`}><div className="image-board"><canvas ref={canvas} width="512" height="512" aria-label="이미지 파츠 겹침 미리보기"/>{guides&&blueprint&&<svg viewBox="0 0 512 512" className="image-anchors" aria-label="공통 연결점">{Object.entries(blueprint.anchors).map(([name,[x,y]])=><g key={name}><circle cx={x} cy={y} r="4"/><path d={`M${x-10} ${y}H${x+10}M${x} ${y-10}V${y+10}`}/><text x={x+8} y={y-8}>{name}</text></g>)}</svg>}</div><div className="image-exploded">{blueprint?.layers.map(l=><button key={l.slot} onClick={()=>{setSelected(l.slot);setExploded(false);}}><LayerThumb layer={l}/><strong>{l.label}</strong><small>{l.asset?'설계 시안':'파츠 이미지 필요'}</small></button>)}</div></div>
        <div className="image-preview-footer"><span>선택한 원본과 생성된 세트 결과를 겹쳐 비교하는 검수 화면</span><button onClick={()=>canvas.current&&downloadCanvas(canvas.current,`${source?.id}-overlay.png`)}>비교 PNG</button><a href={`/api/avatar-blueprints/${source?.id}/recipe`} download>설계 JSON</a></div>
        {blueprint?.source_url&&<div className="image-original"><img src={blueprint.source_url} alt="원본 캐릭터 이미지"/><div><strong>원본 캐릭터</strong><p>생성 시안과 원본을 비교해 정체성·형태·가려진 부분을 확인하세요.</p></div></div>}
      </section><section className="image-layer-panel"><span className="image-kicker">MODULAR LAYERS</span><h2>몸 · 의상 · 무기 · 장비</h2><div className="image-layer-list">{blueprint?.layers.map(l=><div key={l.slot} className={selected===l.slot?'selected':''}><input type="checkbox" aria-label={`${l.label} 표시`} checked={l.visible} onChange={e=>{update({visible:e.target.checked},l.slot);}}/><button onClick={()=>setSelected(l.slot)}><LayerThumb layer={l}/><span>{l.label}<small>{l.asset?'설계 시안 · 검수 전':'이미지 필요'}</small></span></button></div>)}</div>
        {layer&&<div className="image-layer-controls"><h3>{layer.label} 배치</h3><label className="image-description">제작 요청<input aria-label="파츠 제작 요청" maxLength={600} placeholder="예: 파란 수정 지팡이, 작은 별 장식" value={layer.description||''} onChange={e=>update({description:e.target.value})}/></label>{[['X',0,-200,512],['Y',1,-200,512],['너비',2,10,650],['높이',3,10,650]].map(([label,index,min,max])=><label key={String(label)}>{label}<input aria-label={`파츠 ${label}`} type="range" min={min} max={max} value={layer.placement[Number(index)]} onChange={e=>{const placement=[...layer.placement] as ImageLayer['placement'];placement[Number(index)]=Number(e.target.value);update({placement});}}/><output>{Math.round(layer.placement[Number(index)]!)}</output></label>)}<label>겹침 순서<select aria-label="파츠 겹침 순서" value={layer.order} onChange={e=>update({order:Number(e.target.value)})}>{Array.from({length:blueprint?.layers.length||13},(_,i)=><option key={i} value={i}>{i+1} {i===0?'가장 뒤':i===(blueprint?.layers.length||13)-1?'가장 앞':''}</option>)}</select></label><label>배경<select aria-label="파츠 배경 처리" value={layer.background} onChange={e=>update({background:e.target.value as ImageLayer['background']})}><option value="alpha">원본 알파 사용</option><option value="border-gray">회색 배경 마스크 시안</option></select></label><label className="image-upload">선택 파츠 PNG 넣기<input type="file" accept="image/png" aria-label="선택 파츠 PNG 넣기" onChange={e=>{void upload(e.target.files?.[0]);e.target.value='';}}/></label><button disabled={!layer.asset} onClick={()=>void layerBitmap(layer).then(c=>downloadCanvas(c,`${source?.id}-${layer.slot}.png`)).catch(e=>setError(e.message))}>선택 파츠 PNG 받기</button></div>}
      </section></div>{blueprint&&<ImagePipelinePanel key={blueprint.character_id} blueprint={blueprint} dirty={dirty} onBlueprint={b=>{edits.current++;setBlueprint(b);setDirty(b.revision===blueprint.revision);}}/>}<section className="image-next"><div><span>01</span><strong>원본 디자인 기준 6파트</strong><p>대머리 기본몸과 머리카락·모자·상의·하의·신발 이미지를 각각 만들며 숨은 면은 검수 후보로 표시합니다.</p></div><div><span>02</span><strong>파트별 Meshy 3D</strong><p>각 이미지와 작업 ID를 따로 저장합니다. 완료된 PNG·GLB를 파트별로 내려받고 중단된 조회를 복구할 수 있습니다.</p></div><div><span>03</span><strong>기본몸 원본 리그·동작</strong><p>기본몸은 Meshy가 만든 실제 골격·가중치와 저장된 6개 동작을 사용합니다. 임의 본 규격으로 완료 처리하지 않습니다.</p></div></section>
    </main></div>;
}
