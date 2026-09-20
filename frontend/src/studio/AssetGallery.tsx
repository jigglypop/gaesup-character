import { useRef, useState } from 'react';
import { ApiError } from '../api';
import type { FactoryJob, NativePartsState } from '../factory/api';
import { partLabels, variantSlots } from '../factory/parts';
import { isCatalogJobDeleted, studioApi, type Catalog, type PartMetadata } from './api';
import { PartFitting } from './PartFitting';
import { AssetModelPreview } from './AssetModelPreview';
import { AssetProductionStatus } from './AssetProductionStatus';

const assetSlots = ['body', ...variantSlots, 'hairFront', 'hairBack', 'head'];
const partCategories = [
  ['all', '전체'], ['body', '기본몸'], ['hair', '헤어'], ['headwear', '머리·장식'], ['top', '상의'],
  ['bottom', '하의'], ['shoes', '신발'], ['equipment', '장비'],
] as const;

function categoryOf(slot: string) {
  if (['hair', 'hairFront', 'hairBack'].includes(slot)) return 'hair';
  if (['head', 'hat', 'glasses'].includes(slot)) return 'headwear';
  if (['weapon', 'tool'].includes(slot)) return 'equipment';
  return slot;
}

type Props = {
  jobs: FactoryJob[];
  catalog?: Catalog;
  nativeJobId?: string;
  nativeState?: NativePartsState;
  onOpen: (job: FactoryJob) => void;
  onCompose: (job: FactoryJob) => void;
  onCatalogChange: (catalog: Catalog) => void;
  onRefresh: () => Promise<void>;
};

export function AssetGallery({ jobs, catalog, nativeJobId, nativeState, onOpen, onCompose, onCatalogChange, onRefresh }: Props) {
  const [view, setView] = useState<'characters' | 'parts'>('characters');
  const [filter, setFilter] = useState<(typeof partCategories)[number][0]>('all');
  const [characterFilter, setCharacterFilter] = useState('all');
  const [trash, setTrash] = useState(false), [search, setSearch] = useState(''), [visible, setVisible] = useState(24);
  const [editing, setEditing] = useState<{ key: string; name: string; revision: string }>();
  const [fitting, setFitting] = useState<{ key: string; jobId: string; slot: 'top' | 'bottom'; label: string; rawUrl?: string }>();
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [notice, setNotice] = useState('');
  const locked = useRef(false);
  const characterKey = (job: FactoryJob) => job.character_id || job.id;
  const characterDeleted = (job: FactoryJob) => !!catalog?.characters?.[characterKey(job)]?.deleted;
  const jobDeleted = (job: FactoryJob) => isCatalogJobDeleted(job, catalog);
  const byCharacter = new Map<string, FactoryJob>();
  for (const job of [...jobs].sort((a, b) => Number(jobDeleted(b) === trash) - Number(jobDeleted(a) === trash) || b.created_at.localeCompare(a.created_at))) {
    if (!byCharacter.has(characterKey(job))) byCharacter.set(characterKey(job), job);
  }
  const rootFor = (job: FactoryJob) => byCharacter.get(characterKey(job)) || job;
  const characterName = (job: FactoryJob) => {
    const root = rootFor(job);
    return catalog?.parts?.[`${root.id}:body`]?.name || catalog?.items[root.id]?.name || root.character_name;
  };
  const items = jobs.flatMap(job => assetSlots.flatMap(slot => {
    if (job.base_job_id && job.requested_slots && !job.requested_slots.includes(slot)) return [];
    const image = job.artifacts.find(artifact => [`${slot}-front.png`, `${slot}-image.png`].includes(artifact.name));
    const generatedModel = job.artifacts.find(artifact => [`generated-${slot}.glb`, `${slot}.glb`].includes(artifact.name));
    const nativeModel = job.assembly_artifacts?.find(artifact => artifact.name === `${slot}.glb`)
      || (nativeJobId === job.id && nativeState?.status === 'review_required' && nativeState.version === job.assembly_version
        ? nativeState.artifacts.find(artifact => artifact.name === `${slot}.glb`) : undefined);
    if (!image && !generatedModel && !nativeModel && !job.parts?.some(part => part.slot === slot)) return [];
    const key = `${job.id}:${slot}`, metadata = catalog?.parts?.[key], label = partLabels[slot] || slot;
    const name = metadata?.name || `${catalog?.items[job.id]?.name || job.character_name} · ${label}`;
    return [{ key, job, rootId: characterKey(job), slot, category: categoryOf(slot), label, name,
      deleted: !!metadata?.deleted || jobDeleted(job), image, generatedModel, nativeModel }];
  }));
  const roots = [...byCharacter.values()];
  const query = search.trim().toLocaleLowerCase();
  const matchesQuery = (item: (typeof items)[number]) => !query
    || `${item.name} ${item.label} ${characterName(item.job)} ${item.job.id}`.toLocaleLowerCase().includes(query);
  const filtered = items.filter(item => item.deleted === trash
    && (filter === 'all' || item.category === filter)
    && (characterFilter === 'all' || item.rootId === characterFilter) && matchesQuery(item));
  const shown = filtered.slice(0, visible);
  const characterGroups = roots.flatMap(root => {
    const rootMatches = !query || `${characterName(root)} ${root.character_name} ${root.id}`.toLocaleLowerCase().includes(query);
    const availableParts = items.filter(item => item.rootId === characterKey(root) && item.deleted === trash);
    const parts = rootMatches ? availableParts : availableParts.filter(matchesQuery);
    const versions = jobs.filter(job => characterKey(job) === characterKey(root))
      .filter(job => jobDeleted(job) === trash)
      .sort((a, b) => b.created_at.localeCompare(a.created_at));
    if (!parts.length && (!rootMatches || !versions.length)) return [];
    const preview = ['front.png', 'canonical-reference.png', 'reference.png', 'body-front.png']
      .map(name => root.artifacts.find(artifact => artifact.name === name)).find(Boolean)
      || parts.find(item => item.slot === 'body')?.image || parts[0]?.image;
    const assembly = root.assembly_artifacts?.find(artifact => artifact.name === 'model.glb')
      || (nativeJobId === root.id && nativeState?.status === 'review_required' && nativeState.version === root.assembly_version
        ? nativeState.artifacts.find(artifact => artifact.name === 'model.glb') : undefined);
    const generated = root.artifacts.find(artifact => artifact.name === 'generated-body.glb')
      || root.artifacts.find(artifact => /^generated-.+\.glb$/.test(artifact.name));
    const generatedSlot = generated?.name.replace(/^generated-/, '').replace(/\.glb$/, '');
    const model = assembly ? { ...assembly, label: '조립 저장본' }
      : generated ? { ...generated, label: `${partLabels[generatedSlot || ''] || '파츠'} 생성본 · 조립 전` } : undefined;
    return [{ root, parts, versions, preview, assembly, model }];
  });

  async function save(jobId: string, slot: string, changes: PartMetadata, revision = catalog?.revision) {
    if (locked.current || !revision) return;
    locked.current = true; setBusy(true); setError(''); setNotice('');
    try {
      onCatalogChange(await studioApi.savePartMetadata(jobId, slot, changes, revision));
      setEditing(undefined);
      setNotice(changes.deleted === true ? '휴지통으로 이동했습니다.' : changes.deleted === false ? '복원했습니다.' : '이름을 저장했습니다.');
    } catch (e) {
      setError(e instanceof ApiError && e.code === 'revision_conflict' ? '목록이 변경되었습니다. 취소 후 다시 편집해 주세요.' : (e as Error).message);
      await onRefresh();
    } finally { locked.current = false; setBusy(false); }
  }

  async function setVisibility(job: FactoryJob, scope: 'character' | 'version', deleted: boolean) {
    if (locked.current || !catalog) return;
    locked.current = true; setBusy(true); setError(''); setNotice('');
    try {
      onCatalogChange(await studioApi.setVisibility(job.id, scope, deleted, catalog.revision));
      setEditing(undefined);
      setNotice(`${scope === 'character' ? '캐릭터 전체' : '조합 버전'}를 ${deleted ? '휴지통으로 이동했습니다.' : '복원했습니다.'}`);
    } catch (reason) {
      setError((reason as Error).message); await onRefresh();
    } finally { locked.current = false; setBusy(false); }
  }

  function openFitting(jobId: string, slot: 'top' | 'bottom') {
    const item = items.find(candidate => candidate.job.id === jobId && candidate.slot === slot);
    setFitting({ key: `${jobId}:${slot}`, jobId, slot, label: partLabels[slot], rawUrl: item?.image?.url });
  }

  function assetCard(item: (typeof items)[number], compact = false) {
    const { key, job, slot, label, name, image, generatedModel, nativeModel } = item;
    return <article className={`asset-gallery-card ${compact ? 'compact' : ''}`} key={key}>
      <AssetModelPreview model={nativeModel ? { ...nativeModel, label: slot === 'body' ? '기본몸 저장본' : '피팅 저장본' }
        : generatedModel ? { ...generatedModel, label: '파츠 생성본 · 조립 전' } : undefined}
        image={image} name={name} emptyLabel={image ? '3D 생성 전' : '아직 저장된 결과 없음'} />
      <AssetProductionStatus job={job} slot={slot} hasModel={!!(nativeModel || generatedModel)} hasAssembly={!!nativeModel} />
      <div className="asset-gallery-info"><strong title={name}>{name}</strong><span>{label} · {characterName(job)}</span><small>{new Date(job.created_at).toLocaleString()} · {job.id.slice(0, 8)}</small></div>
      {editing?.key === key ? <form className="asset-gallery-edit" onSubmit={event => { event.preventDefault(); void save(job.id, slot, { name: editing.name.trim() }, editing.revision); }}>
        <label>파츠 이름<input autoFocus required maxLength={80} value={editing.name} disabled={busy} onChange={event => setEditing({ ...editing, name: event.target.value })} onKeyDown={event => { if (event.key === 'Escape' && !busy) setEditing(undefined); }} /></label>
        <div><button disabled={busy || !editing.name.trim()}>저장</button><button type="button" disabled={busy} onClick={() => setEditing(undefined)}>취소</button></div>
      </form> : <div className="asset-gallery-actions"><button disabled={busy} onClick={() => { setEditing({ key, name, revision: catalog!.revision }); setError(''); setNotice(''); }}>이름 수정</button>{jobDeleted(job)
        ? <button disabled={busy} onClick={() => void setVisibility(job, characterDeleted(job) ? 'character' : 'version', false)}>{characterDeleted(job) ? '캐릭터 전체 복원' : '조합 복원'}</button>
        : <button className={trash ? '' : 'asset-delete'} disabled={busy} onClick={() => void save(job.id, slot, { deleted: !trash })}>{trash ? '파츠 복원' : '파츠 삭제'}</button>}</div>}
      <div className="asset-gallery-actions"><button onClick={() => onOpen(job)}>작업 열기</button>{(slot === 'top' || slot === 'bottom') && generatedModel && <button onClick={() => openFitting(job.id, slot)}>피팅</button>}{image && <a href={image.url} target="_blank" rel="noreferrer">이미지</a>}{generatedModel && <a href={generatedModel.url} download>생성 GLB</a>}{nativeModel && <a href={nativeModel.url} download>조립 GLB</a>}</div>
    </article>;
  }

  return <section className="asset-gallery" aria-labelledby="asset-gallery-title" aria-busy={busy}>
    <div className="asset-gallery-heading"><h2 id="asset-gallery-title">저장된 캐릭터 에셋</h2>
      <div className="asset-gallery-view-switch" role="group" aria-label="라이브러리 보기"><button aria-pressed={view === 'characters'} onClick={() => setView('characters')}>캐릭터별</button><button aria-pressed={view === 'parts'} onClick={() => setView('parts')}>파츠별</button></div>
    </div>
    {view === 'parts' && <div className="asset-gallery-filters" role="group" aria-label="파츠 분류">{partCategories.map(([key, label]) => <button key={key} aria-pressed={filter === key} onClick={() => { setFilter(key); setVisible(24); }}>{label}</button>)}</div>}
    <div className="asset-gallery-toolbar">
      <label>검색<input type="search" value={search} onChange={event => { setSearch(event.target.value); setVisible(24); }} placeholder="캐릭터 · 파츠" /></label>
      {view === 'parts' && <label>캐릭터<select value={characterFilter} onChange={event => { setCharacterFilter(event.target.value); setVisible(24); }}><option value="all">전체 캐릭터</option>{roots.map(root => <option key={root.id} value={characterKey(root)}>{characterName(root)}</option>)}</select></label>}
      <div className="asset-gallery-filters" role="group" aria-label="보관 위치"><button aria-pressed={!trash} onClick={() => { setTrash(false); setVisible(24); }}>갤러리</button><button aria-pressed={trash} onClick={() => { setTrash(true); setVisible(24); }}>휴지통 · {items.filter(item => item.deleted).length}</button></div>
      <span>{view === 'characters' ? characterGroups.length : filtered.length}개</span>
    </div>
    {error && <p role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}
    {fitting && <PartFitting key={fitting.key} jobId={fitting.jobId} slot={fitting.slot} label={fitting.label} rawUrl={fitting.rawUrl} onClose={() => setFitting(undefined)} onPendingSlot={pendingSlot => openFitting(fitting.jobId, pendingSlot)} />}
    {!catalog ? <p className="asset-gallery-empty">관리 목록 불러오는 중…</p> : view === 'characters' ? characterGroups.length ? <div className="asset-character-grid">{characterGroups.map(({ root, parts, versions, preview, assembly, model }) => <article className="asset-character-card" key={root.id}>
      <AssetModelPreview model={model} image={preview} name={characterName(root)} emptyLabel="아직 저장된 결과 없음" />
      <AssetProductionStatus job={root} hasModel={!!model} hasAssembly={!!assembly} />
      <div className="asset-character-heading"><div><strong>{characterName(root)}</strong><small>{versions.length}개 버전 · {parts.length}개 파츠</small></div><button onClick={() => onOpen(root)}>캐릭터 열기</button></div>
      <div className="asset-character-actions">{!trash && assembly && <button onClick={() => onCompose(root)}>조합·표정 편집</button>}{(!trash || characterDeleted(root)) && <button className={trash ? '' : 'asset-delete'} disabled={busy} onClick={() => void setVisibility(root, 'character', !trash)}>{trash ? '캐릭터 전체 복원' : '캐릭터 전체 삭제'}</button>}</div>
      <div className="asset-character-versions">{versions.map(version => <div className="asset-character-version" key={version.id}><button onClick={() => onOpen(version)}>{version.base_job_id ? version.requested_slots?.map(slot => partLabels[slot] || slot).join(', ') || '파츠 조합' : '기본몸 조합'}<small>{new Date(version.created_at).toLocaleString()}</small></button>{!trash && version.assembly_version && <button onClick={() => onCompose(version)}>조합 편집·저장</button>}{!characterDeleted(version) && <button className={trash ? '' : 'asset-delete'} disabled={busy} onClick={() => void setVisibility(version, 'version', !trash)}>{trash ? '조합 복원' : '조합 삭제'}</button>}</div>)}</div>
      <details><summary>연결 파츠 · {parts.length}</summary><div className="asset-character-parts">{parts.map(item => assetCard(item, true))}</div></details>
    </article>)}</div> : <p className="asset-gallery-empty">{query ? '검색 결과가 없습니다.' : trash ? '삭제한 에셋이 없습니다.' : '저장된 캐릭터가 없습니다.'}</p>
      : filtered.length ? <><div className="asset-gallery-grid">{shown.map(item => assetCard(item))}</div>{visible < filtered.length && <button className="asset-gallery-more" onClick={() => setVisible(count => count + 24)}>더 보기 · {filtered.length-visible}개</button>}</>
        : <p className="asset-gallery-empty">{query ? '검색 결과가 없습니다.' : trash ? '삭제한 에셋이 없습니다.' : '이 분류에 저장된 파츠가 없습니다.'}</p>}
  </section>;
}
