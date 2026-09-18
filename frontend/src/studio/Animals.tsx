import { useEffect, useRef, useState } from 'react';
import { ModelViewer } from '../viewer';
import { usePolling } from '../use-polling';
import { studioApi } from './api';

export default function Animals() {
  const listing=usePolling(studioApi.animals,5000);
  const [species,setSpecies]=useState('dog'),[name,setName]=useState(''),[selected,setSelected]=useState('');
  const [busy,setBusy]=useState(false),[error,setError]=useState('');
  const locked=useRef(false),mount=useRef<HTMLDivElement>(null);
  const animal=listing.value?.items.find(a=>a.id===selected)||listing.value?.items[0];
  const model=animal?.artifacts.find(a=>a.name==='rigged.glb')||animal?.artifacts.find(a=>a.name==='source.glb');
  useEffect(()=>{
    if(!model||!mount.current)return;
    let active=true;const viewer=new ModelViewer(mount.current,'studio');
    void viewer.load(model.url).catch(e=>{if(active)setError(e.message);});
    return()=>{active=false;viewer.dispose();};
  },[model?.url]);
  async function perform(action:()=>Promise<void>){
    if(locked.current)return;locked.current=true;setBusy(true);setError('');
    try{await action();}catch(e){setError((e as Error).message);}finally{locked.current=false;setBusy(false);}
  }
  const statuses:Record<string,string>={uploaded:'원본 저장',accepted:'리깅 대기',running:'리깅 중',complete:'리깅 파일 저장',paused:'리깅 중단',failed:'리깅 실패'};
  return <div className="workspace-content"><h1>동물</h1><div className="texture-form"><label>종류<select disabled={busy} value={species} onChange={e=>setSpecies(e.target.value)}><option value="dog">강아지</option><option value="cat">고양이</option><option value="dragon">용</option></select></label><label>이름<input value={name} maxLength={80} disabled={busy} onChange={e=>setName(e.target.value)} /></label><label>GLB 등록<input type="file" accept=".glb" disabled={busy} onChange={e=>{const file=e.target.files?.[0];e.target.value='';if(!file)return;void perform(async()=>{const result=await studioApi.uploadAnimal(file,species,name.trim()||file.name.replace(/\.glb$/i,''));setSelected(result.id);listing.setValue(current=>({items:[result,...(current?.items||[]).filter(a=>a.id!==result.id)]}));});}} /></label></div>
    <small>정면 +Z · 위 +Y · 네 발이 바닥에 닿는 기본 자세</small>
    {(error||listing.error||animal?.error)&&<p role="alert">{error||listing.error||animal?.error}</p>}
    <div className="asset-grid">{listing.value?.items.map(a=><button className={`asset-card ${animal?.id===a.id?'selected':''}`} key={a.id} onClick={()=>setSelected(a.id)}><strong>{a.name}</strong><small>{statuses[a.status]||a.status}</small></button>)}</div>
    {animal&&<section className="management-panel"><h2>{animal.name}</h2><div ref={mount} className="animal-preview" /><button disabled={busy||['accepted','running','complete'].includes(animal.status)} onClick={()=>void perform(async()=>{await studioApi.rigAnimal(animal.id);await listing.refresh();})}>사족 리깅</button>{animal.bones&&<small> 관절 {animal.bones}개 · 로컬 사족 리깅</small>}<div className="artifact-grid">{animal.artifacts.map(a=><a key={a.name} href={a.url} download>{a.name}</a>)}</div></section>}
  </div>;
}
