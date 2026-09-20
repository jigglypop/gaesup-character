import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { factoryApi, type FactoryJob } from '../factory/api';
import { usePolling } from '../use-polling';
import { meshyOptionsError, type MeshyOptions } from './meshy-options';
import { hairBatchesApi, type HairBatch as HairBatchRecord, type HairSheetItem, type HairView } from './hair-batches-api';
import './hair-batch.css';

const sheetSize = 1254;
const attachedRowEdges = [0,193,388,626,829,1016,1254].map(value => value / sheetSize);
const attachedViewEdges = [
  [0,172,296,424,572,699,830,978,1105,1254],
  [0,170,295,418,590,704,832,981,1105,1254],
  [0,171,294,421,570,694,833,979,1106,1254],
  [0,175,304,432,582,701,835,985,1106,1254],
  [0,168,290,419,571,695,830,984,1109,1254],
  [0,168,285,418,575,696,835,980,1109,1254],
].map(row => row.map(value => value / sheetSize));
const equalEdges = (count: number) => Array.from({length:count+1},(_,index)=>index/count);
const viewLabels: Record<HairView, string> = { front: '정면', back: '후면', side: '측면' };
const stateLabels: Record<string,string> = {accepted:'접수됨',queued:'대기',running:'처리 중',complete:'저장 완료',paused:'이어가기 필요'};
const assetUrl = (id: string) => `/api/avatar-blueprints/assets/${encodeURIComponent(id)}`;
const draftKey = 'gaesup.hair-batch.draft.v1';
type InputMode = 'multi'|'sheet';
type Draft = {mode:InputMode;source:{id:string;name:string}|null;rows:number;columns:number;layout:'attached'|'equal';order:HairView[];removeSkin:boolean;items:HairSheetItem[];selected:number[];concurrency:number};
const emptyDraft: Draft = {mode:'multi',source:null,rows:6,columns:3,layout:'attached',order:['front','back','side'],removeSkin:true,items:[],selected:[],concurrency:4};
function readDraft(): Draft {
  try {
    const value = JSON.parse(localStorage.getItem(draftKey) || 'null') as Partial<Draft> | null;
    if (!value) return emptyDraft;
    const source = value.source && /^[a-f0-9]{64}$/.test(value.source.id) && typeof value.source.name === 'string' ? value.source : null;
    const items = Array.isArray(value.items) && value.items.every(item => typeof item?.name === 'string' && Number.isInteger(item.row) && Number.isInteger(item.column)
      && (['front','side','back'] as const).every(view=>/^[a-f0-9]{64}$/.test(item.views?.[view]))) ? value.items : [];
    const selected = Array.isArray(value.selected) ? value.selected.filter(index=>Number.isInteger(index) && index >= 0 && index < items.length) : [];
    const layout = value.layout === 'equal' ? 'equal' : 'attached';
    const rows = layout === 'attached' ? 6 : Number.isInteger(value.rows) ? Number(value.rows) : 6;
    const columns = layout === 'attached' ? 3 : Number.isInteger(value.columns) ? Number(value.columns) : 3;
    const order = Array.isArray(value.order) && value.order.length === 3 && new Set(value.order).size === 3
      && value.order.every(view=>['front','side','back'].includes(view)) ? value.order as HairView[] : emptyDraft.order;
    const concurrency = [1,2,3,4].includes(Number(value.concurrency)) ? Number(value.concurrency) : 4;
    const mode: InputMode = value.mode === 'sheet' || (!value.mode && source) ? 'sheet' : 'multi';
    return {mode,source,rows,columns,layout,order,removeSkin:value.removeSkin !== false,items,selected,concurrency};
  } catch { return emptyDraft; }
}

export function HairBatch({baseId, version, options, disabled, onJob}: {baseId?: string; version?: string; options: MeshyOptions; disabled: boolean; onJob: (job: FactoryJob) => void}) {
  const readBatches = useCallback((signal: AbortSignal) => hairBatchesApi.list(signal), []);
  const batches = usePolling(readBatches, 5000);
  const initialRecovery = useRef(hairBatchesApi.recovery());
  const initialDraft = useRef(readDraft());
  const [mode,setMode] = useState<InputMode>(initialDraft.current.mode);
  const [source, setSource] = useState(initialDraft.current.source);
  const [rows,setRows] = useState(initialDraft.current.rows), [columns,setColumns] = useState(initialDraft.current.columns);
  const [layout,setLayout] = useState<'attached'|'equal'>(initialDraft.current.layout);
  const [order,setOrder] = useState<HairView[]>(initialDraft.current.order), [removeSkin,setRemoveSkin] = useState(initialDraft.current.removeSkin);
  const [items,setItems] = useState<HairSheetItem[]>(initialDraft.current.items), [selected,setSelected] = useState<number[]>(initialDraft.current.selected);
  const [concurrency,setConcurrency] = useState(initialDraft.current.concurrency), [busy,setBusy] = useState(false), [error,setError] = useState('');
  const [pending,setPending] = useState(initialRecovery.current.pending);
  const submitLock = useRef(false);
  const resumeLocks = useRef(new Set<string>());
  const [uploadProgress,setUploadProgress] = useState('');
  const recoveryError = initialRecovery.current.error;
  const rowEdges = useMemo(() => layout === 'attached' ? attachedRowEdges : equalEdges(rows), [layout, rows]);
  const validGrid = Number.isInteger(rows) && rows >= 1 && rows <= 12 && Number.isInteger(columns) && columns >= 1 && columns <= 8 && rows * columns <= 48;
  useEffect(() => {
    try { localStorage.setItem(draftKey, JSON.stringify({mode,source,rows,columns,layout,order,removeSkin,items,selected,concurrency} satisfies Draft)); }
    catch { /* Draft persistence must not block batch controls. */ }
  }, [mode, source, rows, columns, layout, order, removeSkin, items, selected, concurrency]);
  async function upload(file?: File) {
    if (!file) return; setBusy(true);setError('');
    try { const result = await hairBatchesApi.uploadSheet(file); setSource({id:result.id,name:file.name});setItems([]);setSelected([]); }
    catch(e){setError((e as Error).message);} finally{setBusy(false);}
  }
  async function split() {
    if(!source)return;setBusy(true);setError('');
    try {
      if (!validGrid) throw new Error('행 1~12, 스타일 1~8, 전체 48종 이하로 입력하세요.');
      const result = await hairBatchesApi.splitSheet({asset_id:source.id,rows,columns,row_edges:rowEdges,
        ...(layout === 'attached' ? {view_edges:attachedViewEdges} : {}),view_order:order,remove_skin:removeSkin});
      setItems(result.items);setSelected(result.items.map((_,i)=>i));
    } catch(e){setError((e as Error).message);} finally{setBusy(false);}
  }
  async function uploadMultiple(files: File[]) {
    if (!files.length) return;
    const ordered = [...files].sort((a,b)=>a.name.localeCompare(b.name,undefined,{numeric:true,sensitivity:'base'}));
    if (ordered.length > 48) { setError('3뷰 이미지는 한 번에 최대 48개까지 선택하세요.'); return; }
    setBusy(true);setError('');setSource(null);setItems([]);setSelected([]);setUploadProgress(`0 / ${ordered.length}`);
    const completed: Array<HairSheetItem|undefined> = new Array(ordered.length);
    const failures: Array<string|undefined> = new Array(ordered.length);
    let cursor=0,done=0;
    const worker = async () => {
      while (true) {
        const index=cursor++;
        if(index>=ordered.length)return;
        const file=ordered[index];
        try {
          const uploaded=await hairBatchesApi.uploadSheet(file);
          const splitResult=await hairBatchesApi.splitSheet({asset_id:uploaded.id,rows:1,columns:1,row_edges:[0,1],view_order:order,remove_skin:false,detect_view_seams:true});
          const item=splitResult.items[0];
          if(!item)throw new Error('분할 결과가 없습니다.');
          completed[index]={...item,row:index+1,name:(file.name.replace(/\.[^.]+$/,'').trim()||`헤어 ${index+1}`).slice(0,100)};
          const visible=completed.filter((value):value is HairSheetItem=>!!value);
          setItems(visible);setSelected(visible.map((_,itemIndex)=>itemIndex));
        } catch { failures[index]=file.name; }
        finally { done++;setUploadProgress(`${done} / ${ordered.length}`); }
      }
    };
    try {
      await Promise.all(Array.from({length:Math.min(3,ordered.length)},()=>worker()));
      const failed=failures.filter((value):value is string=>!!value);
      if(failed.length)setError(`${failed.length}개 파일을 처리하지 못했습니다: ${failed.join(', ')}`);
    } finally { setBusy(false);setUploadProgress(''); }
  }
  async function generate() {
    if(submitLock.current)return;submitLock.current=true;setBusy(true);setError('');
    try {
      if (!pending) {
        if(!baseId || !version || !selected.length)throw new Error('기준 몸과 생성할 스타일을 선택하세요.');
        if(meshyOptionsError(options))throw new Error(meshyOptionsError(options));
      }
      const input = pending?.input || {base_job_id:baseId!,base_version:version!,items:selected.map(i=>({name:items[i].name.trim(),views:items[i].views})),concurrency,meshy_options:options};
      const created = await hairBatchesApi.create(input);
      setPending(null);
      batches.setValue(current => ({items:[created, ...(current?.items || []).filter(batch => batch.id !== created.id)]}));
      void batches.refresh();
    }catch(e){setPending(hairBatchesApi.recovery().pending);setError((e as Error).message);}finally{submitLock.current=false;setBusy(false);}
  }
  async function resume(id:string){
    if(resumeLocks.current.has(id))return;
    resumeLocks.current.add(id);setBusy(true);setError('');
    try {
      const resumed=await hairBatchesApi.resume(id);
      batches.setValue(current=>({items:(current?.items || []).map(batch=>batch.id===id?resumed:batch)}));
      void batches.refresh();
    }catch(e){setError((e as Error).message);}finally{resumeLocks.current.delete(id);setBusy(false);}
  }
  async function open(jobId:string){try{onJob(await factoryApi.detail(jobId));}catch(e){setError((e as Error).message);}}
  function useEqualGrid(nextRows = rows, nextColumns = columns) {
    setRows(nextRows); setColumns(nextColumns); setLayout('equal'); setItems([]); setSelected([]);
  }
  return <section className="hair-batch"><h2>헤어 일괄 생성</h2>
    <fieldset disabled={busy || !!pending || disabled || !!recoveryError}>
      <label>입력 방식<select value={mode} onChange={event=>{setMode(event.target.value as InputMode);setSource(null);setItems([]);setSelected([]);setError('');}}><option value="multi">3뷰 이미지 여러 장</option><option value="sheet">한 장 시트</option></select></label>
      {mode==='multi' ? <label>3뷰 이미지<input type="file" multiple accept="image/png,image/jpeg" onChange={event=>void uploadMultiple(Array.from(event.target.files||[]))}/></label> : <>
      <label>원본 시트<input type="file" accept="image/png,image/jpeg" onChange={event=>void upload(event.target.files?.[0])}/></label>
      {source && <small>{source.name} · 업로드 완료</small>}
      <label>시트 레이아웃<select value={layout} onChange={event=>{const next=event.target.value as typeof layout;setLayout(next);setRows(6);setColumns(3);setItems([]);setSelected([]);}}><option value="attached">첨부 헤어 시트 · 18종</option><option value="equal">등간격</option></select></label>
      <div className="hair-batch-grid"><label>행<input type="number" min={1} max={12} value={rows} onChange={e=>useEqualGrid(Number(e.target.value),columns)}/></label><label>한 행 스타일 수<input type="number" min={1} max={8} value={columns} onChange={e=>useEqualGrid(rows,Number(e.target.value))}/></label></div></>}
      <label>각 스타일의 뷰 순서<select value={order.join(',')} onChange={e=>setOrder(e.target.value.split(',') as HairView[])}><option value="front,back,side">정면 · 후면 · 측면</option><option value="front,side,back">정면 · 측면 · 후면</option></select></label>
      {mode==='sheet' && <><label className="hair-batch-check"><input type="checkbox" checked={removeSkin} onChange={e=>setRemoveSkin(e.target.checked)}/>피부·배경 잔여색 제외</label>
      {!validGrid && <small role="alert">행 1~12, 스타일 1~8, 전체 48종 이하로 입력하세요.</small>}
      <button disabled={!source || !validGrid} onClick={()=>void split()}>시트 자르기</button></>}
      {!!items.length && <div className="hair-batch-selection"><span>{items.length}종 중 {selected.length}종 선택</span><button type="button" onClick={()=>setSelected(selected.length===items.length?[]:items.map((_,i)=>i))}>{selected.length===items.length?'전체 해제':'전체 선택'}</button></div>}
      {items.map((item,index)=><article className="hair-batch-item" key={`${item.row}:${item.column}`}><label className="hair-batch-check"><input type="checkbox" checked={selected.includes(index)} onChange={e=>setSelected(current=>e.target.checked?[...current,index]:current.filter(i=>i!==index))}/><input aria-label={`스타일 ${index+1} 이름`} value={item.name} maxLength={100} onChange={e=>setItems(current=>current.map((v,i)=>i===index?{...v,name:e.target.value}:v))}/></label><div className="hair-batch-views">{(['front','back','side'] as const).map(view=><figure key={view}><img src={assetUrl(item.views[view])} loading="lazy" alt={`${item.name} ${viewLabels[view]}`}/><figcaption>{viewLabels[view]}</figcaption></figure>)}</div></article>)}
      <label>동시 처리<select value={concurrency} onChange={e=>setConcurrency(Number(e.target.value))}>{[1,2,3,4].map(n=><option key={n} value={n}>{n}개</option>)}</select></label>
    </fieldset>
    {uploadProgress && <p role="status">3뷰 이미지 처리 중 · {uploadProgress}</p>}
    <button disabled={busy || !!recoveryError || (!pending && (disabled || !baseId || !version || !selected.length || selected.some(index=>!items[index].name.trim())))} onClick={()=>void generate()}>{pending?'같은 요청 키로 접수 복구':`${selected.length}종 생성 · Meshy ${selected.length}회`}</button>
    {pending && <small className="generation-recovery">응답이 확인되지 않은 배치입니다. 입력과 요청 키를 유지해 결과를 복구합니다.</small>}
    {(error || recoveryError || batches.error) && <p role="alert">{error || recoveryError || batches.error}</p>}
    {batches.loading && !batches.value && <p>배치 목록 불러오는 중</p>}
    {!batches.loading && !batches.value?.items.length && <p>저장된 헤어 배치가 없습니다.</p>}
    {batches.value?.items.map((batch:HairBatchRecord)=><details key={batch.id} open={batch.status!=='complete'}><summary>{batch.input.items.length}종 · {batch.completed} 저장 · {stateLabels[batch.status] || batch.status}</summary>
      {batch.error && <p role="alert">{batch.error}</p>}
      {batch.items.map(item=><article className="hair-batch-item" key={item.index}><div className="hair-batch-views">{(['front','back','side'] as const).map(view=><figure key={view}><img src={assetUrl(batch.input.items[item.index].views[view])} loading="lazy" alt={`${item.name} ${viewLabels[view]}`}/><figcaption>{viewLabels[view]}</figcaption></figure>)}</div><strong>{item.name}</strong><small>{stateLabels[item.status] || item.status}{item.progress?.message ? ` · ${item.progress.message}` : ''}</small>{(item.error||item.state_error) && <p role="alert">{item.error||item.state_error}</p>}<button disabled={item.status==='queued' || !item.job_id} onClick={()=>void open(item.job_id)}>결과 보기</button></article>)}
      {batch.can_resume && <button disabled={busy} onClick={()=>void resume(batch.id)}>저장된 작업 이어가기</button>}
    </details>)}
  </section>;
}
