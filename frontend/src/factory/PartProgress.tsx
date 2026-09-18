import type { FactoryJob } from './api';

const labels: Record<string, string> = { body: '몸', hair: '머리카락', head: '기존 머리 파츠', hairBack: '뒷머리', hairFront: '앞머리', hat: '모자', top: '상의', bottom: '하의', shoes: '신발' };

export function PartProgress({ job, busy, retryImage }: { job: FactoryJob; busy: boolean; retryImage: (slot: string, view: string, failureId: string) => Promise<void> }) {
  const parts = job.parts || [];
  const imageStates = parts.flatMap(p => Object.values(p.views || {}).length ? Object.values(p.views!) : [{status: p.image_status}]);
  const images = imageStates.filter(image => ['received', 'succeeded', 'qc_failed'].includes(image.status)).length;
  const models = parts.filter(p => p.model_status === 'ready').length;
  const imageNames: Record<string, string> = { pending: '대기', not_sent: '연결 실패', submitting: '응답 대기', received: '수신 · 저장 중', succeeded: '수신 완료', submission_uncertain: '연결 끊김', rejected: '요청 거부', failed: '처리 실패', qc_failed: '수신 · 처리 대기' };
  const modelNames: Record<string, string> = { pending: '대기', PENDING: '접수됨', IN_PROGRESS: '생성 중', SUCCEEDED: '다운로드 중', ready: '파일 수신 완료', submission_uncertain: '응답 확인 필요', submission_rejected: '요청 거부', FAILED: '실패', CANCELED: '취소됨' };
  return <section className="character-progress" aria-label="파츠 수신 현황">
    <h2>파츠 수신 현황</h2>
    <p role="status">수신 이미지 {images}/{imageStates.length} · 3D {models}/{parts.length}</p>
    <ul>{parts.map(part => {
      const views = Object.keys(part.views || {});
      const assets = views.length ? views.flatMap(view => {
        const asset = job.artifacts.find(a => a.name === `${part.slot}-${view}.png`);
        return asset ? [{ ...asset, label: view === 'front' ? '정면' : '측면' }] : [];
      }) : job.artifacts.filter(a => a.name === `${part.slot}-image.png`).map(a => ({ ...a, label: '이미지' }));
      const model = job.artifacts.find(a => a.name === `generated-${part.slot}.glb`);
      return <li key={part.slot} data-part-slot={part.slot}>
        {assets.length > 0 && <div className="part-view-images">{assets.map(asset => <a key={asset.name} href={asset.url} target="_blank" rel="noreferrer"><img src={asset.url} alt={`${labels[part.slot] || part.slot} ${asset.label}`} loading="lazy" /><span>{asset.label}</span></a>)}</div>}
        <div><strong>{labels[part.slot] || part.slot}</strong>
          {!Object.keys(part.views || {}).length && <span>이미지 · {imageNames[part.image_status] || part.image_status}</span>}
          {Object.entries(part.views || {}).map(([view, image]) => {
            const action = job.next_actions?.find(a => a.id === 'retry_image' && a.enabled && a.slot === part.slot && a.view === view);
            return <div className="part-view" key={view}>
              <span>{view === 'front' ? '정면' : '측면'} · {image.status === 'rejected' && image.failure?.message ? image.failure.message : imageNames[image.status] || image.status}</span>
              {action?.failure_id && <button className="part-retry" disabled={busy} onClick={() => void retryImage(part.slot, view, action.failure_id!)}>{busy ? '접수 중' : '다시 요청 · 유료 1장'}</button>}
            </div>;
          })}
          <span>3D · {modelNames[part.model_status] || part.model_status}{part.model_status === 'IN_PROGRESS' && ` ${part.progress || 0}%`}</span>
          {model && <a href={model.url} download>파츠 GLB</a>}
        </div>
      </li>;
    })}</ul>
    <small>작업 {job.id}</small>
  </section>;
}
