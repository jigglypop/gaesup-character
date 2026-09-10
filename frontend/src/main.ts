import { api, ApiError, type Character } from './api';
import type { ModelViewer } from './viewer';
import './style.css';

const app = document.querySelector<HTMLDivElement>('#app')!;
const escape = (value: unknown) => String(value ?? '').replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[ch]!);
const statusNames: Record<string, string> = { ready: '준비됨', blocked: '입력 / 확인 필요', in_progress: '작업 중', review_required: '검수 대기', approved: '승인됨' };
const roleNames: Record<string, string> = { body: '몸', head: '머리', hair: '헤어', hat: '모자', top: '상의', pants: '바지', skirt: '치마', dress: '원피스', shoes: '신발', outfit_base: '원래 의상', accessory: '액세서리', eyes: '눈', other: '기타' };
let characters: Character[] = [], selected = decodeURIComponent(location.hash.slice(1)), current: Character | null = null;
let viewer: ModelViewer | null = null, loading = false, submitting = false, timer: ReturnType<typeof setTimeout> | undefined;
let viewGeneration = 0, editingParts = false;
let renderedRevision: string | undefined, renderedId: string | undefined;

app.innerHTML = `
  <aside class="sidebar">
    <a class="brand" href="#"><span class="brand-icon">a</span><span>atelier<span class="brand-dot">.</span></span></a>
    <div class="workspace-label">CHARACTER WORKSPACE</div>
    <nav aria-label="워크스페이스"><button class="nav-item active" id="nav-library"><span>◈</span> 캐릭터 라이브러리 <span class="nav-count">0</span></button></nav>
    <div class="sidebar-note"><span class="tiny-label">YOUR WORKFLOW</span><p>하나의 캐릭터에서<br>다양한 가능성으로.</p><div class="workflow-mini">생성 <span>→</span> 리깅 <span>→</span> 파츠 <span>→</span> 검수</div></div>
    <div class="sidebar-footer"><span class="avatar">CW</span><div>Character Wardrobe<small>로컬 워크스페이스</small></div></div>
  </aside>
  <main>
    <header class="topbar"><span>워크스페이스 <span class="separator">/</span> <b>캐릭터 라이브러리</b></span><button id="refresh" class="quiet"><span id="connection-dot" class="dot"></span><span id="connection-label">연결 중</span> <span class="refresh-symbol">↻</span></button></header>
    <div class="content">
      <section class="page-heading"><div><p class="eyebrow">BUILD A CHARACTER. MAKE IT YOURS.</p><h1>캐릭터 라이브러리<span class="heading-dot">.</span></h1><p class="subtitle">캐릭터의 시작부터 파츠 분리, 마지막 검수까지 한곳에서.</p></div><button class="primary" id="new-character"><span>＋</span> 캐릭터 등록</button></section>
      <div id="notice" class="notice" role="status" aria-live="polite" hidden></div>
      <section aria-label="라이브러리 요약" id="summary" class="summary"></section>
      <div class="section-label"><h2>캐릭터 컬렉션 <span id="collection-count">0</span></h2><span>소스와 작업 기록이 함께 보관됩니다</span></div>
      <section id="cards" class="cards" aria-label="캐릭터 목록"><div class="empty">캐릭터를 불러오는 중입니다…</div></section>
      <section id="detail" aria-label="캐릭터 상세"></section>
      <footer class="page-footer"><span>ATELIER / CHARACTER WARDROBE</span><span>기술 검증과 시각적 완성을 각각 확인합니다.</span></footer>
    </div>
  </main>
  <dialog id="create-dialog"><form id="create-form"><div class="dialog-heading"><div><p class="eyebrow">NEW CHARACTER</p><h2>새 캐릭터 등록</h2></div><button type="button" class="icon-button" id="close-dialog" aria-label="닫기">×</button></div><p class="muted">캐릭터를 등록한 후 이미지 또는 리깅된 GLB를 가져오세요.</p><label>캐릭터 이름<input name="name" required maxlength="80" placeholder="예: 토끼 캐릭터" /></label><label>키 (m)<input name="height" type="number" min="0.1" max="100" step="0.01" placeholder="나중에 입력할 수 있어요" /></label><p class="form-hint">등록은 Meshy 생성 요청을 시작하지 않습니다.</p><button class="primary full" type="submit">캐릭터 등록</button><p id="create-error" class="error-text" role="alert"></p></form></dialog>`;

const notice = (message: string, error = false) => {
  const element = document.querySelector<HTMLElement>('#notice')!;
  element.textContent = message; element.hidden = !message; element.classList.toggle('error', error);
};
const badge = (c: Character) => `<span class="badge ${escape(c.pipeline_status)}"><i></i>${escape(statusNames[c.pipeline_status] || c.pipeline_status)}</span>`;

function renderCards() {
  document.querySelector('.nav-count')!.textContent = String(characters.length);
  document.querySelector('#collection-count')!.textContent = String(characters.length);
  const count = (state: string) => characters.filter(c => c.pipeline_status === state).length;
  document.querySelector('#summary')!.innerHTML = `<div><span class="stat-icon">◈</span><p>전체 캐릭터<strong>${characters.length.toString().padStart(2, '0')}</strong></p></div><div><span class="stat-icon lavender">↗</span><p>작업 중<strong>${count('in_progress').toString().padStart(2, '0')}</strong></p></div><div><span class="stat-icon amber">◷</span><p>검수 대기<strong>${count('review_required').toString().padStart(2, '0')}</strong></p></div><div><span class="stat-icon green">✓</span><p>승인 완료<strong>${count('approved').toString().padStart(2, '0')}</strong></p></div>`;
  document.querySelector('#cards')!.innerHTML = characters.length ? characters.map((c, i) => {
    const image = c.artifacts.find(a => a.id === 'reference');
    return `<button class="character-card ${c.id === selected ? 'selected' : ''}" data-id="${escape(c.id)}" aria-pressed="${c.id === selected}"><div class="card-visual tone-${i % 5}"><span class="character-number">${String(i + 1).padStart(2, '0')}</span>${image ? `<img src="${escape(image.url)}" alt="${escape(c.name)} 소스" loading="lazy" />` : '<span class="no-image">◇</span>'}<span class="card-arrow">↗</span></div><div class="card-info"><strong>${escape(c.name)}</strong>${badge(c)}</div></button>`;
  }).join('') : '<div class="empty"><h3>첫 번째 캐릭터를 만나볼까요?</h3><p>이미지 또는 리깅된 GLB를 등록해 작업을 시작하세요.</p></div>';
  document.querySelectorAll<HTMLButtonElement>('.character-card').forEach(button => button.onclick = () => { selected = button.dataset.id!; location.hash = selected; current = characters.find(c => c.id === selected)!; renderCards(); renderDetail(); });
}

async function renderDetail() {
  editingParts = false; viewer?.dispose(); viewer = null;
  const generation = ++viewGeneration;
  const c = current;
  renderedRevision = c?.revision; renderedId = c?.id;
  const element = document.querySelector<HTMLElement>('#detail')!;
  if (!c) { element.innerHTML = ''; return; }
  const model = c.artifacts.find(a => a.id === c.model_id);
  const source = c.artifacts.find(a => a.id === 'reference');
  const metrics = c.inspection.metrics;
  const busy = ['accepted', 'running', 'recovery_required'].includes(c.operation?.status || '');
  const rig = { meshy: 'Meshy 기본 리깅', local_fallback: '로컬 리깅 · 검수 필요', unknown: '출처 확인 전' }[c.rig_origin] || c.rig_origin;
  const rawActions = c.next_actions.filter(a => !['organize_parts', 'record_review', 'separate_parts'].includes(a.id));
  element.innerHTML = `<div class="detail-heading"><div><span class="eyebrow">CHARACTER STUDIO</span><h2>${escape(c.name)} <span class="id-label">${escape(c.id)}</span></h2></div>${badge(c)}</div>
    <div class="studio-grid"><div class="preview-panel"><div class="preview-toolbar"><span class="preview-label"><i></i>${model ? '3D PREVIEW' : 'SOURCE PREVIEW'}</span><select id="model-select" aria-label="미리보기 모델">${c.artifacts.filter(a => a.kind === 'model').map(a => `<option value="${escape(a.url)}" ${a.id === c.model_id ? 'selected' : ''}>${escape({ local_fallback: '로컬 리깅 모델', generated: '생성 원본', rigged: 'Meshy 리깅', imported: '가져온 GLB', walking: '걷기', running: '달리기', parts_model: '파츠 모델' }[a.id] || a.id)}</option>`).join('') || '<option>입력 이미지</option>'}</select></div><div id="viewer" class="viewer">${!model ? source ? `<img class="source-preview" src="${escape(source.url)}" alt="캐릭터 입력 이미지" />` : '<div class="preview-empty"><span>◇</span><h3>캐릭터의 시작을 가져오세요</h3><p>이미지 또는 리깅된 GLB를 업로드해 주세요.</p></div>' : '<div id="model-loading" class="model-loading">3D 모델을 불러오는 중…</div>'}</div><div class="preview-bottom"><span>${model ? '드래그하여 회전 · 스크롤하여 확대' : '원본 이미지 보존'}</span><select id="animation" aria-label="애니메이션"><option value="-1">기본 자세</option></select></div></div>
    <div class="inspector"><div class="panel-heading"><h3>캐릭터 설정</h3><span class="small-label">OVERVIEW</span></div><form id="settings-form"><label>이름<input name="name" aria-label="캐릭터 이름" required maxlength="80" value="${escape(c.name)}" /></label><div class="field-row"><label>키 (m)<input name="height" aria-label="캐릭터 키" type="number" min="0.1" max="100" step="any" value="${c.height_meters ?? ''}" placeholder="예: 1.7" ${c.provider.status ? 'readonly' : ''} /></label><label>리깅 출처<div class="read-value">${escape(rig)}</div></label></div><button type="submit" class="secondary full" ${busy ? 'disabled' : ''}>설정 저장</button></form>
    <div class="inspector-section"><h3>소스 가져오기</h3><p class="muted small">이미지는 생성에, 리깅된 GLB는 바로 파츠 작업에 사용합니다.</p><div class="upload-row"><label class="upload-button ${c.provider.status || busy ? 'disabled' : ''}">↥ 이미지<input type="file" id="image-file" accept="image/png,image/jpeg" ${c.provider.status || busy ? 'disabled' : ''}/></label><label class="upload-button ${c.provider.status || busy ? 'disabled' : ''}">↥ 리깅 GLB<input type="file" id="model-file" accept=".glb" ${c.provider.status || busy ? 'disabled' : ''}/></label></div></div>
    <div class="inspector-section"><h3>다음 작업</h3><div class="actions">${rawActions.map(a => `<button type="button" class="${a.external_mutation ? 'primary' : 'secondary'} full" data-action="${escape(a.id)}" ${!a.enabled ? 'disabled' : ''} title="${escape(a.reason || '')}">${escape(a.label)}${a.external_mutation ? '<span class="paid-tag">유료</span>' : '<span>↗</span>'}</button>${a.reason && !a.enabled ? `<p class="form-hint">${escape(a.reason)}</p>` : ''}`).join('') || '<p class="muted small">소스와 키를 입력하면 가능한 작업이 표시됩니다.</p>'}</div></div></div></div>
    <div class="detail-lower"><div class="panel"><div class="panel-heading"><h3>작업 기록</h3><span class="small-label">PIPELINE</span></div><div class="pipeline-stages">${['소스', '리깅', '파츠', '검수'].map((label, i) => `<div class="pipeline-step ${[!!source || !!model, c.rig_origin !== 'unknown', c.parts.length > 0, c.review.decision === 'approved'][i] ? 'done' : ''}"><span>${i + 1}</span>${label}</div>`).join('')}</div>${c.problems.map(p => `<div class="problem"><span>!</span><p>${escape(p.message)}</p></div>`).join('')}${c.operation ? `<div class="operation"><b>${escape({ accepted: '작업 수락됨', running: '실행 중', succeeded: '작업 완료', failed: '작업 실패', recovery_required: '기존 작업 확인 필요' }[c.operation.status] || c.operation.status)}</b><code>${escape(c.operation.action_id)}</code>${c.operation.error ? `<p>${escape(c.operation.error.message)}</p>` : ''}</div>` : '<p class="muted small">실행한 작업이 이곳에 기록됩니다.</p>'}${c.provider.status ? `<div class="provider"><span>Meshy ${escape(c.provider.stage)}</span><code>${escape(c.provider.status)}</code>${c.provider.progress != null ? `<progress value="${c.provider.progress}" max="100"></progress>` : ''}${c.provider.task_id ? `<span class="task-id">Task ${escape(c.provider.task_id)}</span>` : ''}</div>` : ''}<div id="pending-recovery"></div></div>
    <div class="panel"><div class="panel-heading"><h3>모델 검사</h3><span class="small-label">QUALITY</span></div><div class="quality-stats"><div><strong>${metrics ? metrics.vertices.toLocaleString() : '—'}</strong><span>정점</span></div><div><strong>${metrics ? metrics.triangles.toLocaleString() : '—'}</strong><span>삼각형</span></div><div><strong>${metrics ? metrics.joints.length : '—'}</strong><span>관절</span></div><div><strong>${metrics ? metrics.animations.length : '—'}</strong><span>동작</span></div></div><p class="quality-note">${c.inspection.errors ? c.inspection.errors.length ? `구조 오류: ${escape(c.inspection.errors.join(', '))}` : '구조 검사 통과 · 외형과 동작은 별도로 확인하세요.' : '모델 검사를 실행하면 구조와 파츠 정보를 확인할 수 있습니다.'}</p>${c.model_sha256 ? `<div class="hash-label">SHA256 <code>${escape(c.model_sha256.slice(0, 24))}…</code></div>` : ''}</div></div>
    ${c.inspection.nodes ? `<div class="panel parts-panel"><div class="panel-heading"><div><h3>파츠와 검수</h3><p class="muted small">현재 GLB에 분리되어 있는 메시의 역할을 지정합니다.</p></div><span class="small-label">PARTS & REVIEW</span></div><div class="parts-grid"><form id="parts-form"><div class="part-rows">${c.inspection.nodes.map(node => `<div class="part-row"><input type="checkbox" checked data-visible="${escape(node.name)}" aria-label="${escape(node.name)} 표시" /><span>${escape(node.name)}<small>${node.skinned ? 'SKINNED' : 'MESH'}</small></span><select name="node-${node.index}" aria-label="${escape(node.name)} 역할">${Object.entries(roleNames).map(([key, label]) => `<option value="${key}" ${c.parts.find(p => p.node_index === node.index)?.role === key ? 'selected' : ''}>${label}</option>`).join('')}</select></div>`).join('')}</div><label>몸의 coverage<select name="coverage"><option value="unknown">확인 전</option><option value="partial" ${c.body_coverage === 'partial' ? 'selected' : ''}>부분 — 원래 옷 아래 몸이 없음</option><option value="full" ${c.body_coverage === 'full' ? 'selected' : ''}>전체 — 옷 아래 몸까지 있음</option></select></label><button class="secondary" type="submit" ${!c.next_actions.find(a => a.id === 'organize_parts')?.enabled ? 'disabled' : ''}>파츠 역할 저장</button><p class="form-hint">붙어 있는 메시의 새로운 분리는 Blender 편집이 필요합니다.</p></form><form id="review-form"><label>검수 메모<textarea name="notes" minlength="5" maxlength="2000" required placeholder="외형과 주요 동작에서 확인한 내용을 기록하세요.">${escape(c.review.notes || '')}</textarea></label><label class="check-label"><input type="checkbox" name="appearance" /> 캐릭터 외형과 의상 경계를 확인했습니다</label><label class="check-label"><input type="checkbox" name="motion" /> 대상 동작에서 관통과 변형을 확인했습니다</label><div class="review-buttons"><button type="submit" name="decision" value="changes_requested" class="secondary">수정 요청</button><button type="submit" name="decision" value="approved" class="primary" ${!c.next_actions.find(a => a.id === 'record_review')?.enabled ? 'disabled' : ''}>현재 버전 승인</button></div>${c.review.decision ? `<p class="form-hint">최근 검수: ${c.review.decision === 'approved' ? '승인' : '수정 요청'} · ${escape(c.review.reviewed_at)}</p>` : ''}</form></div></div>` : ''}`;
  document.querySelector<HTMLFormElement>('#settings-form')!.onsubmit = async event => {
    event.preventDefault(); const form = new FormData(event.currentTarget as HTMLFormElement);
    await mutation(() => api.update(c, String(form.get('name')), form.get('height') ? Number(form.get('height')) : null), '설정을 저장했습니다.');
  };
  for (const kind of ['image', 'model']) document.querySelector<HTMLInputElement>(`#${kind}-file`)!.onchange = async event => {
    const file = (event.target as HTMLInputElement).files?.[0]; if (file) await mutation(() => api.upload(c, file, kind), '소스를 등록했습니다.');
  };
  element.querySelectorAll<HTMLButtonElement>('[data-action]').forEach(button => button.onclick = () => {
    if (button.dataset.action === 'recover_task') {
      const task = window.prompt('기존 Meshy 작업 ID를 입력하세요. 새 작업을 생성하지 않습니다.');
      if (task) void submitAction('recover_task', { task_id: task });
    } else if (button.dataset.action === 'recover_motion_task') {
      const slot = Object.entries(c.motion_pack.tasks).find(([, task]) => task.status === 'submission_uncertain')?.[0];
      const task = window.prompt(`${slot} 단계의 기존 Meshy 작업 ID를 입력하세요.`);
      if (slot && task) void submitAction('recover_motion_task', { slot, task_id: task });
    } else if (button.dataset.action === 'submit_generation') {
      void submitAction('submit_generation', { profile: document.querySelector<HTMLSelectElement>('#generation-profile')?.value || 'meshy-7' });
    } else if (button.dataset.action === 'prepare_character') {
      void submitAction('prepare_character', { max_new_tasks: 6, actions: { idle: 0, walk: 1, run: 14, jump: 466, fall: 502 } });
    } else void submitAction(button.dataset.action!);
  });
  document.querySelector<HTMLFormElement>('#parts-form')?.addEventListener('submit', event => {
    event.preventDefault(); const form = new FormData(event.currentTarget as HTMLFormElement);
    void submitAction('organize_parts', { parts: c.inspection.nodes!.map(node => ({ node_index: node.index, role: form.get(`node-${node.index}`) })), body_coverage: form.get('coverage') });
  });
  document.querySelector<HTMLFormElement>('#review-form')?.addEventListener('submit', event => {
    event.preventDefault(); const form = new FormData(event.currentTarget as HTMLFormElement);
    void submitAction('record_review', { decision: (event.submitter as HTMLButtonElement).value, notes: form.get('notes'), motion_checked: form.has('motion'), appearance_checked: form.has('appearance') });
  });
  element.querySelectorAll<HTMLInputElement>('[data-visible]').forEach(input => {
    const node = c.inspection.nodes?.find(node => node.name === input.dataset.visible);
    input.onchange = () => { if (node) viewer?.setVisible(node.index, input.checked); };
  });
  const outputs = c.artifacts.filter(a => ['parts_blend', 'rest_render'].includes(a.id) || a.id === c.model_id);
  if (model) {
    document.querySelector('.preview-label')!.innerHTML = '<i></i>GAESUP WORLD';
    document.querySelector('.preview-bottom > span')!.textContent = '월드 클릭 후 WASD 이동 · Shift 달리기 · Space 점프';
    document.querySelector('.preview-toolbar')!.insertAdjacentHTML('beforeend', '<button type="button" id="expand-world" class="secondary">크게 보기</button>');
    document.querySelector<HTMLButtonElement>('#expand-world')!.onclick = () => {
      const panel = document.querySelector<HTMLElement>('.preview-panel')!;
      panel.classList.toggle('world-expanded');
      document.querySelector('#expand-world')!.textContent = panel.classList.contains('world-expanded') ? '닫기' : '크게 보기';
    };
  }
  document.querySelector('.quality-note')?.insertAdjacentHTML('afterend', `<div class="artifact-links">${outputs.map(a => `<a href="${escape(a.url)}" target="_blank" rel="noopener">${a.id === 'parts_blend' ? 'Blender 작업 파일 ↗' : a.id === 'rest_render' ? '기본 자세 렌더 ↗' : '현재 GLB 받기 ↗'}</a>`).join('')}</div>`);
  if (c.motion_pack?.status) document.querySelector('#pending-recovery')!.insertAdjacentHTML('beforebegin', `<div class="motion-status"><h3>기본 동작 패키지</h3><p>${escape(c.motion_pack.status)} · 새 요청 ${c.motion_pack.submitted_tasks}/${c.motion_pack.max_new_tasks}</p>${['idle','walk','run','jump','fall'].map(slot => `<span class="motion-slot">${slot} · ${c.motion_pack.clips[slot] ? '다운로드됨' : escape(c.motion_pack.tasks[slot]?.status || '대기')}</span>`).join('')}</div>`);
  if (model && c.next_actions.some(a => a.id === 'separate_parts' && a.enabled)) {
    document.querySelector('.preview-bottom')!.insertAdjacentHTML('afterend', `<div class="part-editor"><button id="edit-parts" class="secondary">파츠 영역 편집</button><div id="paint-tools" hidden><div class="paint-row"><label>파츠<select id="paint-role">${Object.entries(roleNames).map(([role,name]) => `<option value="${role}" ${role === 'hair' ? 'selected' : ''}>${name}</option>`).join('')}</select></label><label>브러시<input id="paint-size" type="range" min="1" max="15" value="4" /></label><label><input type="checkbox" id="paint-erase" /> 지우기</label></div><p class="form-hint">왼쪽 드래그로 원본 면 선택 · 오른쪽 드래그로 회전 · 휠 확대. 선택하지 않은 면은 기타 파츠로 보존됩니다.</p><div class="paint-row"><button class="quiet" id="paint-undo">되돌리기</button><button class="quiet" id="paint-clear">선택 지우기</button><span id="paint-count">0개 면 선택</span><button id="split-painted" class="primary" disabled>선택 영역 분리</button></div></div></div>`);
    document.querySelector<HTMLButtonElement>('#edit-parts')!.onclick = () => {
      editingParts = !editingParts; document.querySelector<HTMLElement>('#paint-tools')!.hidden = !editingParts;
      document.querySelector('#edit-parts')!.textContent = editingParts ? '월드로 돌아가기' : '파츠 영역 편집';
      document.querySelector<HTMLSelectElement>('#animation')!.disabled = editingParts;
      document.querySelector<HTMLSelectElement>('#model-select')!.disabled = editingParts;
      viewer?.setEditing(editingParts, count => { document.querySelector('#paint-count')!.textContent = `${count.toLocaleString()}개 면 선택`; document.querySelector<HTMLButtonElement>('#split-painted')!.disabled = count === 0; });
    };
    const settings = () => viewer?.setPaint({ role: document.querySelector<HTMLSelectElement>('#paint-role')!.value, radius: Number(document.querySelector<HTMLInputElement>('#paint-size')!.value) / 100, erase: document.querySelector<HTMLInputElement>('#paint-erase')!.checked });
    for (const id of ['paint-role','paint-size','paint-erase']) document.querySelector(`#${id}`)!.addEventListener('input', settings);
    document.querySelector<HTMLButtonElement>('#paint-undo')!.onclick = () => viewer?.undoPaint();
    document.querySelector<HTMLButtonElement>('#paint-clear')!.onclick = () => viewer?.clearPaint();
    document.querySelector<HTMLButtonElement>('#split-painted')!.onclick = () => {
      const selections = viewer?.selections(); if (selections?.length) void submitAction('separate_parts', { source_sha256: c.model_sha256, selections });
    };
  }
  document.querySelector('[data-action="prepare_character"]')?.insertAdjacentHTML('afterend', '<p class="form-hint">유료: 리깅 최대 1회 + 동작 최대 5회. idle(0), walk(1), run(14), jump(466), fall(502). 기존 walk/run은 재사용하며 실패를 자동 재제출하지 않습니다.</p>');
  document.querySelector('[data-action="submit_generation"]')?.insertAdjacentHTML('beforebegin', '<label>생성 방식<select id="generation-profile"><option value="smart-topology">Smart Topology · 분리된 파츠 · 15,000면</option><option value="meshy-7">Meshy 7 · 디테일 · 30,000면</option></select></label>');
  renderRecovery();
  if (model) {
    try {
      const { ModelViewer } = await import('./viewer');
      if (generation !== viewGeneration) return;
      viewer = new ModelViewer(document.querySelector<HTMLElement>('#viewer')!);
      const activeViewer = viewer;
      const load = async (url: string) => {
        try {
          const clips = await activeViewer.load(url);
          if (generation !== viewGeneration) return;
          document.querySelector('#model-loading')?.remove();
          document.querySelector<HTMLSelectElement>('#animation')!.innerHTML = '<option value="-1">기본 자세</option>' + clips.map(clip => `<option value="${clip.index}">${escape(clip.name)}</option>`).join('');
        } catch (error) { if (generation === viewGeneration) notice((error as Error).message, true); }
      };
      document.querySelector<HTMLSelectElement>('#animation')!.onchange = event => activeViewer.play(Number((event.target as HTMLSelectElement).value));
      document.querySelector<HTMLSelectElement>('#model-select')!.onchange = event => {
        const url = (event.target as HTMLSelectElement).value;
        const canonical = url === model.url;
        const editorButton = document.querySelector<HTMLButtonElement>('#edit-parts'); if (editorButton) editorButton.disabled = !canonical;
        document.querySelectorAll<HTMLButtonElement>('#review-form button').forEach(button => { button.disabled = !canonical || !c.next_actions.find(a => a.id === 'record_review')?.enabled; });
        document.querySelectorAll<HTMLInputElement>('[data-visible]').forEach(input => { input.disabled = !canonical; input.checked = true; });
        if (!canonical) notice('다른 산출물을 미리 보는 중입니다. 현재 버전으로 돌아오면 검수를 기록할 수 있습니다.');
        void load(url);
      };
      await load(model.url);
    } catch { notice('3D 미리보기를 시작하지 못했습니다. 브라우저의 WebGL 지원을 확인해 주세요.', true); }
  }
}

async function mutation(work: () => Promise<Character>, message: string) {
  if (submitting) return; submitting = true;
  try { current = await work(); selected = current.id; location.hash = selected; notice(message); await refresh(false); }
  catch (error) { notice((error as Error).message, true); if (error instanceof ApiError && error.status === 409) await refresh(false); }
  finally { submitting = false; }
}

type Pending = { id: string; action: string; payload: object; key: string; revision: string };
const pendingKey = 'atelier.pending-action';
function readPending(): Pending | null { try { return JSON.parse(sessionStorage.getItem(pendingKey) || 'null'); } catch { return null; } }
function renderRecovery() {
  const pending = readPending(), container = document.querySelector('#pending-recovery');
  if (!container || !pending || pending.id !== current?.id) return;
  container.innerHTML = '<p class="form-hint">응답을 받지 못한 요청이 있습니다. 같은 식별자로 기존 수락 기록을 확인합니다.</p><button class="secondary" id="recover-request">요청 상태 복구</button>';
  document.querySelector<HTMLButtonElement>('#recover-request')!.onclick = () => void submitAction(pending.action, pending.payload, pending);
}
async function submitAction(action: string, payload: object = {}, recover?: Pending) {
  if (!current || submitting) return;
  if (!recover && readPending()) { notice('응답을 받지 못한 기존 요청부터 복구해 주세요.', true); renderRecovery(); return; }
  submitting = true;
  const pending = recover || { id: current.id, action, payload, key: crypto.randomUUID(), revision: current.revision };
  sessionStorage.setItem(pendingKey, JSON.stringify(pending));
  try {
    await api.action({ ...current, id: pending.id, revision: pending.revision }, action, pending.payload, pending.key);
    sessionStorage.removeItem(pendingKey); notice('작업을 수락했습니다. 진행 상황을 자동으로 확인합니다.'); await refresh(false);
  } catch (error) {
    if (error instanceof ApiError && error.status >= 400 && error.status < 500) sessionStorage.removeItem(pendingKey);
    notice((error as Error).message, true); await refresh(false); renderRecovery();
  } finally { submitting = false; }
}

async function refresh(automatic = true) {
  if (loading) return; loading = true;
  try {
    const result = await api.list(); characters = result.characters;
    if (!characters.some(c => c.id === selected)) selected = characters[0]?.id || '';
    const fresh = characters.find(c => c.id === selected) || null;
    const changed = fresh?.revision !== renderedRevision || fresh?.id !== renderedId;
    const editing = ['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName || '');
    current = fresh; renderCards();
    if (!automatic || (changed && !editing && !editingParts)) void renderDetail();
    document.querySelector('#connection-label')!.textContent = '동기화됨'; document.querySelector('#connection-dot')!.classList.add('online');
  } catch (error) {
    notice((error as Error).message, true); document.querySelector('#connection-label')!.textContent = '연결 확인'; document.querySelector('#connection-dot')!.classList.remove('online');
  } finally {
    loading = false; clearTimeout(timer); timer = setTimeout(() => void refresh(), characters.some(c => ['accepted', 'running'].includes(c.operation?.status || '')) ? 1500 : 10000);
  }
}

document.querySelector<HTMLButtonElement>('#refresh')!.onclick = () => void refresh(false);
document.querySelector<HTMLButtonElement>('#nav-library')!.onclick = () => window.scrollTo({ top: 0, behavior: 'smooth' });
const dialog = document.querySelector<HTMLDialogElement>('#create-dialog')!;
document.querySelector<HTMLButtonElement>('#new-character')!.onclick = () => { document.querySelector<HTMLFormElement>('#create-form')!.reset(); document.querySelector('#create-error')!.textContent = ''; dialog.showModal(); };
document.querySelector<HTMLButtonElement>('#close-dialog')!.onclick = () => dialog.close();
document.querySelector<HTMLFormElement>('#create-form')!.onsubmit = async event => {
  event.preventDefault(); const form = new FormData(event.currentTarget as HTMLFormElement);
  const button = (event.currentTarget as HTMLFormElement).querySelector<HTMLButtonElement>('[type=submit]')!; button.disabled = true;
  try { current = await api.create(String(form.get('name')), form.get('height') ? Number(form.get('height')) : null); selected = current.id; location.hash = selected; dialog.close(); notice('캐릭터를 등록했습니다. 소스를 가져와 작업을 시작하세요.'); await refresh(false); }
  catch (error) { document.querySelector('#create-error')!.textContent = (error as Error).message; }
  finally { button.disabled = false; }
};
window.addEventListener('hashchange', () => { const id = decodeURIComponent(location.hash.slice(1)); if (id && id !== selected) { selected = id; void refresh(false); } });
window.addEventListener('pagehide', () => { clearTimeout(timer); viewer?.dispose(); });
void refresh(false);
