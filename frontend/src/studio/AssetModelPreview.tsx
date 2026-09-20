import { useEffect, useMemo, useRef, useState } from 'react';
import type { CardView } from '../viewer';
import './asset-model-preview.css';

export type AssetPreviewModel = { url: string; sha256?: string; label: string; name?: string };
export type AssetModelPreviewProps = {
  model?: AssetPreviewModel;
  models?: AssetPreviewModel[];
  image?: { url: string };
  name: string;
  emptyLabel: string;
  detail?: boolean;
};

type View = 'model' | 'image';

const modelIdentity = (model: AssetPreviewModel) => `${model.url}:${model.sha256 ?? ''}`;

export function AssetModelPreview({ model, models, image, name, emptyLabel, detail = false }: AssetModelPreviewProps) {
  const viewerMount = useRef<HTMLDivElement>(null);
  const viewer = useRef<import('../viewer').ModelViewer | null>(null);
  const nameRef = useRef(name);
  nameRef.current = name;
  const choices = useMemo(() => models?.length ? models : model ? [model] : [], [model, models]);
  const choicesKey = choices.map(modelIdentity).join('|');
  const [selectedModel, setSelectedModel] = useState(() => choices[0] ? modelIdentity(choices[0]) : '');
  const activeModel = choices.find(item => modelIdentity(item) === selectedModel) || choices[0];
  const [visible, setVisible] = useState(false);
  const [view, setView] = useState<View>(activeModel ? 'model' : 'image');
  const [cardView, setCardView] = useState<CardView>('front');
  const [loading, setLoading] = useState(false);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  const modelUrl = activeModel?.url;
  const modelSha256 = activeModel?.sha256;
  const modelLabel = activeModel?.label;
  const modelKey = useMemo(() => modelUrl ? `${modelUrl}:${modelSha256 ?? ''}` : '', [modelSha256, modelUrl]);

  useEffect(() => {
    setSelectedModel(current => choices.some(item => modelIdentity(item) === current) ? current : choices[0] ? modelIdentity(choices[0]) : '');
  }, [choicesKey]);

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
    let instance: import('../viewer').ModelViewer | undefined;
    setLoading(true);
    setReady(false);
    setError('');
    void import('../viewer').then(({ ModelViewer }) => {
      if (!active) return;
      instance = new ModelViewer(element, 'card');
      viewer.current = instance;
      const canvas = element.querySelector('canvas');
      canvas?.setAttribute('aria-label', `${nameRef.current} 3D 모델. 드래그하여 회전하고 휠로 확대 또는 축소합니다.`);
      let timeoutId: ReturnType<typeof setTimeout>;
      const timeout = new Promise<never>((_, reject) => {
        timeoutId = setTimeout(() => reject(new Error('3D 미리보기를 20초 안에 준비하지 못했습니다.')), 20_000);
      });
      return Promise.race([instance.load(modelUrl, { sha256: modelSha256 }), timeout])
        .finally(() => clearTimeout(timeoutId));
    }).then(() => {
      if (!active) return;
      setReady(true);
      setLoading(false);
    }).catch(reason => {
      if (!active) return;
      instance?.dispose();
      instance = undefined;
      viewer.current = null;
      setLoading(false);
      setReady(false);
      setError(reason instanceof Error ? reason.message : String(reason));
    });
    return () => {
      active = false;
      instance?.dispose();
      if (viewer.current === instance) viewer.current = null;
    };
  }, [attempt, modelKey, modelSha256, modelUrl, view, visible]);

  useEffect(() => { viewer.current?.setCardView(cardView); }, [cardView, ready]);

  useEffect(() => {
    viewerMount.current?.querySelector('canvas')?.setAttribute('aria-label', `${name} 3D 모델. 드래그하여 회전하고 휠로 확대 또는 축소합니다.`);
  }, [name, ready]);

  const showImage = Boolean(image) && (view === 'image' || !ready);
  const source = view === 'image' && image ? '이미지 · 2D'
    : error ? image ? '3D 로드 실패 · 2D 이미지' : '3D 로드 실패'
      : !ready ? image ? '3D 불러오는 중 · 2D 이미지' : modelUrl ? '3D 불러오는 중' : undefined
        : modelLabel;

  return <div className={`asset-model-preview ${detail ? 'detail' : ''}`} aria-busy={loading}>
    {showImage && <img src={image!.url} alt={`${name} 2D 이미지`} loading="lazy" />}
    {!image && (!activeModel || !visible || loading || error) && <div className="asset-model-preview-empty">{activeModel ? loading ? '3D 불러오는 중' : error ? '3D 미리보기 오류' : '3D 미리보기 준비 중' : emptyLabel}</div>}
    <div className="asset-model-preview-canvas" ref={viewerMount} />
    {source && <span className="asset-model-preview-source">{source}</span>}
    {modelUrl && image && <button type="button" className="asset-model-preview-toggle" aria-pressed={view === 'image'} onClick={() => { setLoading(false); setReady(false); setView(current => current === 'model' ? 'image' : 'model'); }}>{view === 'model' ? '2D 보기' : '3D 보기'}</button>}
    {detail && choices.length > 1 && <div className="asset-model-preview-models" role="group" aria-label="3D 파일 선택">{choices.map(item => <button type="button" key={modelIdentity(item)} aria-pressed={modelIdentity(item) === modelIdentity(activeModel!)} onClick={() => { setSelectedModel(modelIdentity(item)); setView('model'); }}>{item.name || item.label}</button>)}</div>}
    {detail && modelUrl && view === 'model' && <div className="asset-model-preview-views" role="group" aria-label="카메라 방향">{([['front','정면'],['side','측면'],['back','후면']] as const).map(([key,label]) => <button type="button" key={key} aria-pressed={cardView === key} onClick={() => setCardView(key)}>{label}</button>)}</div>}
    {error && view === 'model' && <div className="asset-model-preview-error" role="alert"><span>3D 미리보기 로드 실패</span><small>{error}</small><button type="button" onClick={() => setAttempt(value => value + 1)}>다시 시도</button></div>}
  </div>;
}
