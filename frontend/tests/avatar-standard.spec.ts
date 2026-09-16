import { test, expect } from '@playwright/test';

test('fixed-body factory reports live API validation and survives reconnect', async ({ page, request }) => {
  await page.goto('/avatar.html');
  await page.getByRole('link', { name: '고정 몸 · 공용 골격', exact: true }).click();
  await expect(page.getByRole('heading', { name: '고정 몸 · 공용 골격 공장' })).toBeVisible();
  await expect(page.getByRole('button', { name: '기준 몸 템플릿 생성', exact: true })).toBeDisabled();
  const response = await request.post('/api/avatar-standard/bases', {
    headers: { 'Idempotency-Key': 'browser-invalid-base' },
    data: { character_id: 'missing', source_sha256: '0'.repeat(64), name: 'invalid', height_m: 1.2, command: 'forbidden' },
  });
  expect(response.status()).toBe(422);
  await page.route('**/api/avatar-standard/items', route => route.abort());
  await expect(page.getByRole('alert').filter({ hasText: '연결' })).toBeVisible({ timeout: 10000 });
  await page.unroute('**/api/avatar-standard/items');
  await expect(page.getByRole('alert')).toHaveCount(0, { timeout: 10000 });
  await page.reload();
  await expect(page.getByRole('heading', { name: '고정 몸 · 공용 골격 공장' })).toBeVisible();
});

test('real Blender shared skeleton, two outfits, animation and persisted preview', async ({ page, request }) => {
  test.skip(!process.env.WORKSPACE_TEST_STANDARD_ROOT, 'Run run_avatar_standard_check.py with disposable data.');
  const { items } = await request.get('/api/avatar-standard/items').then(r => r.json());
  const outfits = items.filter((i: any) => i.kind === 'assembly');
  expect(outfits).toHaveLength(2);
  for (const outfit of outfits) {
    expect(outfit.status).toBe('review_required');
    await page.goto(`/avatar.html?stage=standard&item=${outfit.id}`);
    await expect(page.getByRole('heading', { name: outfit.name, exact: true })).toBeVisible();
    await expect(page.getByLabel('공용 골격 동작').locator('option')).toHaveCount(8);
    await page.getByLabel('공용 골격 동작').selectOption({ label: 'walk' });
    const scene = page.locator('.standard-scene');
    await expect(scene).toHaveAttribute('data-renderer', /webgpu|webgl-fallback/);
    const backend = await scene.getAttribute('data-renderer');
    await expect(scene.locator('.renderer-badge')).toHaveText(backend === 'webgpu' ? 'WebGPU · gaesup-world' : 'WebGL 호환 모드 · gaesup-world');
    await expect(scene.locator('.renderer-badge')).toBeVisible();
    console.log(`Standard outfit ${outfit.id}: ${backend}`);
    const result = await page.evaluate(async (url: string) => {
      const loaderPath = '/node_modules/three/examples/jsm/loaders/GLTFLoader.js';
      const threePath = '/node_modules/three/build/three.module.js';
      const { GLTFLoader } = await import(loaderPath); const THREE = await import(threePath);
      const gltf = await new GLTFLoader().loadAsync(url);
      const meshes: any[] = []; gltf.scene.traverse((o: any) => { if (o.isSkinnedMesh) meshes.push(o); });
      const first = meshes[0].skeleton.bones;
      const shared = meshes.every(m => m.skeleton.bones.every((b: any, i: number) => b === first[i]));
      const parts = meshes.filter(m => m.userData.standard_slot);
      if (!parts.length) throw new Error('Bound part metadata missing');
      const snapshot = () => parts.flatMap(part => Array.from({ length: part.geometry.attributes.position.count }, (_, i) => {
        const v = new THREE.Vector3().fromBufferAttribute(part.geometry.attributes.position, i); part.applyBoneTransform(i, v); return v.applyMatrix4(part.matrixWorld);
      }));
      gltf.scene.updateMatrixWorld(true); meshes.forEach(m => m.skeleton.update());
      const before = snapshot();
      const mixer = new THREE.AnimationMixer(gltf.scene);
      const clipName = parts[0].userData.standard_slot === 'hat' ? 'jump' : 'walk';
      const clip = gltf.animations.find((a: any) => a.name === clipName);
      mixer.clipAction(clip).play(); mixer.update(.23);
      gltf.scene.updateMatrixWorld(true); meshes.forEach(m => m.skeleton.update());
      const after = snapshot();
      const maxMovement = Math.max(...after.map((v: any, i: number) => v.distanceTo(before[i])));
      const height = new THREE.Box3().setFromObject(gltf.scene).getSize(new THREE.Vector3()).y;
      mixer.stopAllAction(); mixer.uncacheRoot(gltf.scene);
      return { shared, boneCount: first.length, maxMovement, height, clips: gltf.animations.length };
    }, outfit.artifacts.find((a: any) => a.name === 'model.glb').url);
    expect(result.shared).toBe(true); expect(result.boneCount).toBe(24);
    expect(result.maxMovement).toBeGreaterThan(.001); expect(result.clips).toBe(7);
    expect(result.height).toBeGreaterThan(1); expect(result.height).toBeLessThan(1.5);
    await page.reload();
    await expect(page.locator('[data-standard-preview]')).toHaveAttribute('data-standard-preview', outfit.id);
    await expect(page.getByLabel('공용 골격 동작').locator('option')).toHaveCount(8);
    await expect(page.locator('.standard-scene')).toHaveAttribute('data-renderer', /webgpu|webgl-fallback/);
  }
  await page.screenshot({ path: 'test-results/avatar-standard-outfit.png', fullPage: true });
});

test('canonical template upload persists crop and paid shape input stays bounded', async ({ page, request }) => {
  test.skip(!process.env.WORKSPACE_TEST_STANDARD_ROOT, 'Requires the disposable canonical fixture.');
  const { items } = await request.get('/api/avatar-standard/items').then(r => r.json());
  const base = items.find((i: any) => i.kind === 'base' && i.status === 'approved');
  const png = await request.get(base.artifacts.find((a: any) => a.name === 'front.png').url).then(r => r.body());
  await page.goto(`/avatar.html?stage=standard&item=${base.id}`);
  await page.getByLabel('동일 물체 식별자').fill('browser-shirt');
  await page.getByLabel('2048px 파츠 PNG').setInputFiles({ name: 'fixture-front.png', mimeType: 'image/png', buffer: png });
  await page.getByLabel('잘라내기 x,y,너비,높이').fill('400,600,800,400');
  await page.getByRole('button', { name: '원본 좌표와 생성용 시안 저장' }).click();
  await expect(page.getByRole('heading', { name: 'browser-shirt front', exact: true })).toBeVisible();
  const imageId = new URL(page.url()).searchParams.get('item');
  const image = await request.get(`/api/avatar-standard/items/${imageId}`).then(r => r.json());
  expect(image.result.crop_scale).toBe(1.28); expect(image.result.export_offset_px).toEqual([0, 256]);
  await page.reload();
  await expect(page.getByRole('heading', { name: 'browser-shirt front', exact: true })).toBeVisible();
  const generate = page.getByRole('button', { name: 'Meshy 7 파츠 생성 · 유료 1회', exact: true });
  await expect(generate).toBeDisabled();
  await page.getByRole('checkbox', { name: 'browser-shirt front', exact: true }).check();
  await expect(generate).toBeEnabled();
  await generate.click();
  await expect(page.getByRole('alert')).toContainText('Meshy 키 설정');
  const after = await request.get('/api/avatar-standard/items').then(r => r.json());
  expect(after.items.filter((i: any) => i.kind === 'shape')).toHaveLength(0);
});

test('generated design uses measured points and publishes an aligned, source-bound view', async ({ page, request }) => {
  test.skip(!process.env.WORKSPACE_TEST_STANDARD_ROOT, 'Requires the disposable canonical fixture.');
  const { items } = await request.get('/api/avatar-standard/items').then(r => r.json());
  const design = items.find((i: any) => i.kind === 'design');
  expect(design).toBeTruthy();
  await page.goto(`/avatar.html?stage=standard&item=${design.id}`);
  const align = page.getByRole('button', { name: '측정점으로 정렬하고 생산 시안 저장', exact: true });
  await expect(align).toBeDisabled();
  for (const [i, point] of ['824,1250', '1224,1250', '848,1630'].entries()) {
    await page.getByLabel(`source 기준점 ${i + 1}`, { exact: true }).fill(point);
    await page.getByLabel(`target 기준점 ${i + 1}`, { exact: true }).fill(point);
  }
  await page.getByRole('checkbox', { name: '배경·몸 없이 요청한 파츠 하나만 포함됨' }).check();
  await page.getByRole('checkbox', { name: '같은 디자인의 시점·착용 위치·입구를 확인함' }).check();
  await expect(align).toBeEnabled();
  await page.getByLabel('source 기준점 1', { exact: true }).fill('824,');
  await expect(align).toBeDisabled();
  await page.getByLabel('source 기준점 1', { exact: true }).fill('824,1250');
  await expect(align).toBeEnabled();
  await page.screenshot({ path: 'test-results/avatar-standard-design-alignment.png', fullPage: true });
  await align.click();
  await expect(page.getByRole('heading', { name: 'fixture-shirt front', exact: true })).toBeVisible();
  const id = new URL(page.url()).searchParams.get('item');
  const result = await request.get(`/api/avatar-standard/items/${id}`).then(r => r.json());
  expect(result.lineage.design_id).toBe(design.id);
  expect(result.lineage.source_sha256).toBe(design.result.image_asset);
  expect(result.lineage.alignment.scale).toBe(1);
  expect(result.lineage.alignment.errors_px).toEqual([0, 0, 0]);
  await page.reload();
  await expect(page.getByRole('heading', { name: 'fixture-shirt front', exact: true })).toBeVisible();
});
