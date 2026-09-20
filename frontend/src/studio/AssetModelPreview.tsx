import { useEffect, useMemo, useRef, useState } from 'react';
import './asset-model-preview.css';

export type AssetModelPreviewProps = {
  model?: { url: string; sha256?: string; label: string };
  image?: { url: string };
  name: string;
  emptyLabel: string;
};

type View = 'model' | 'image';

export function AssetModelPreview({ model, image, name, emptyLabel }: AssetModelPreviewProps) {
  const viewerMount = useRef<HTMLDivElement>(null);
  const nameRef = useRef(name);
  nameRef.current = name;
  const [visible, setVisible] = useState(false);
  const [view, setView] = useState<View>(model ? 'model' : 'image');
  const [loading, setLoading] = useState(false);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  const modelUrl = model?.url;
  const modelSha256 = model?.sha256;
  const modelLabel = model?.label;
  const modelKey = useMemo(() => modelUrl ? `${modelUrl}:${modelSha256 ?? ''}` : '', [modelSha256, modelUrl]);

  useEffect(() => {
    const element = viewerMount.current;
    if (!element) return;
    const observer = new IntersectionObserver(entries => {
      const nextVisible = entries.some(entry => entry.isIntersecting);
      setVisible(nextVisible);
      if (!nextVisible) { setLoading(false); setReady(false); }
    }, { threshold: 0.01 });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    setView(modelUrl ? 'model' : 'image');
    setLoading(false);
    setReady(false);
    setError('');
    setAttempt(0);
  }, [modelKey, modelUrl]);

  useEffect(() => {
    const element = viewerMount.current;
    if (!element || !modelUrl || view !== 'model' || !visible) return;
    let active = true;
    let viewer: import('../viewer').ModelViewer | undefined;
    setLoading(true);
    setReady(false);
    setError('');
    void import('../viewer').then(({ ModelViewer }) => {
      if (!active) return;
      viewer = new ModelViewer(element, 'card');
      const canvas = element.querySelector('canvas');
      canvas?.setAttribute('aria-label', `${nameRef.current} 3D 모델. 드래그하여 회전하고 휠로 확대 또는 축소합니다.`);
      let timeoutId: ReturnType<typeof setTimeout>;
      const timeout = new Promise<never>((_, reject) => {
        timeoutId = setTimeout(() => reject(new Error('3D 미리보기를 20초 안에 준비하지 못했습니다.')), 20_000);
      });
      return Promise.race([viewer.load(modelUrl, { sha256: modelSha256 }), timeout])
        .finally(() => clearTimeout(timeoutId));
    }).then(() => {
      if (!active) return;
      setReady(true);
      setLoading(false);
    }).catch(reason => {
      if (!active) return;
      viewer?.dispose();
      viewer = undefined;
      setLoading(false);
      setReady(false);
      setError(reason instanceof Error ? reason.message : String(reason));
    });
    return () => {
      active = false;
      viewer?.dispose();
    };
  }, [attempt, modelKey, modelSha256, modelUrl, view, visible]);

  useEffect(() => {
    viewerMount.current?.querySelector('canvas')?.setAttribute('aria-label', `${name} 3D 모델. 드래그하여 회전하고 휠로 확대 또는 축소합니다.`);
  }, [name, ready]);

  const showImage = Boolean(image) && (view === 'image' || !ready);
  const source = view === 'image' && image ? '이미지 · 2D'
    : error ? image ? '3D 로드 실패 · 2D 이미지' : '3D 로드 실패'
      : !ready ? image ? '3D 불러오는 중 · 2D 이미지' : modelUrl ? '3D 불러오는 중' : undefined
        : modelLabel;

  return <div className="asset-model-preview" aria-busy={loading}>
    {showImage && <img src={image!.url} alt={`${name} 2D 이미지`} loading="lazy" />}
    {!image && (!model || !visible || loading || error) && <div className="asset-model-preview-empty">{model ? loading ? '3D 불러오는 중' : error ? '3D 미리보기 오류' : '3D 미리보기 준비 중' : emptyLabel}</div>}
    <div className="asset-model-preview-canvas" ref={viewerMount} />
    {source && <span className="asset-model-preview-source">{source}</span>}
    {modelUrl && image && <button type="button" className="asset-model-preview-toggle" aria-pressed={view === 'image'} onClick={() => { setLoading(false); setReady(false); setView(current => current === 'model' ? 'image' : 'model'); }}>{view === 'model' ? '2D 보기' : '3D 보기'}</button>}
    {error && view === 'model' && <div className="asset-model-preview-error" role="alert"><span>3D 미리보기 로드 실패</span><small>{error}</small><button type="button" onClick={() => setAttempt(value => value + 1)}>다시 시도</button></div>}
  </div>;
}
