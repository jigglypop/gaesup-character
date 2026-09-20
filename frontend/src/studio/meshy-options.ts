import { useMemo, useState } from 'react';

export type MeshyOptions = {
  ai_model: 'meshy-7.1'; geometry_resolution: 'standard' | '2k';
  should_texture: boolean; enable_pbr: boolean; texture_resolution: '2k' | '4k' | '8k';
  texture_mode: 'source' | 'prompt' | 'image' | 'images'; texture_image_assets: string[];
  should_remesh: boolean; topology: 'triangle' | 'quad'; target_polycount: number;
  decimation_mode: 1 | 2 | 3 | 4 | null; save_pre_remeshed_model: boolean;
  pose_mode: '' | 'a-pose' | 't-pose'; image_enhancement: boolean; remove_lighting: boolean;
  moderation: boolean; target_formats: ('glb' | 'obj' | 'fbx' | 'stl' | 'usdz' | '3mf')[];
  auto_size: boolean; origin_at: 'bottom' | 'center'; alpha_thumbnail: boolean; multi_view_thumbnails: boolean;
};
export const defaultMeshyOptions: MeshyOptions = {
  ai_model: 'meshy-7.1', geometry_resolution: '2k', should_texture: true, enable_pbr: true,
  texture_resolution: '4k', texture_mode: 'source', texture_image_assets: [], should_remesh: false,
  topology: 'triangle', target_polycount: 30000, decimation_mode: null, save_pre_remeshed_model: false,
  pose_mode: '', image_enhancement: false, remove_lighting: true, moderation: false,
  target_formats: ['glb'], auto_size: false, origin_at: 'bottom', alpha_thumbnail: false, multi_view_thumbnails: false,
};
const key = (scope: string) => `gaesup.meshy-7.1:${scope}`;
export function useMeshyOptions(scope: string) {
  const initial = useMemo(() => {
    try {
      const saved = { ...defaultMeshyOptions, ...JSON.parse(localStorage.getItem(key(scope)) || '{}') } as MeshyOptions;
      if (!Number.isFinite(saved.target_polycount)) saved.target_polycount = defaultMeshyOptions.target_polycount;
      if (!Array.isArray(saved.texture_image_assets)) saved.texture_image_assets = [];
      if (!Array.isArray(saved.target_formats)) saved.target_formats = ['glb'];
      if (!saved.target_formats.includes('glb')) saved.target_formats.unshift('glb');
      return saved;
    }
    catch { return defaultMeshyOptions; }
  }, [scope]);
  const [drafts, setDrafts] = useState<Record<string, MeshyOptions>>({});
  const [storageError, setStorageError] = useState('');
  return { options: drafts[scope] || initial, storageError, setOptions: (value: MeshyOptions) => {
    setDrafts(current => ({ ...current, [scope]: value }));
    try { localStorage.setItem(key(scope), JSON.stringify(value)); setStorageError(''); }
    catch { setStorageError('Meshy 설정을 브라우저에 저장하지 못했습니다.'); }
  } };
}
export function meshyOptionsError(value: MeshyOptions) {
  if (value.should_remesh && value.decimation_mode === null
    && (!Number.isInteger(value.target_polycount) || value.target_polycount < 100 || value.target_polycount > 300000)) return '목표 폴리곤을 100~300,000 사이 정수로 입력하세요.';
  const count = value.texture_image_assets.length;
  if (value.should_texture && ((value.texture_mode === 'image' && count !== 1) || (value.texture_mode === 'images' && (count < 1 || count > 4)))) return '텍스처 참조 이미지를 선택하세요. 단일 1장 / 다중 1~4장.';
  return '';
}
