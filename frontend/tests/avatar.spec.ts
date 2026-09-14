import { test, expect } from '@playwright/test';

test('avatar outfit uses live API, preserves animation, rolls back failed loads, saves and restores', async ({ page, request }) => {
  const current = await request.get('/api/avatars/me').then(response => response.json());
  await request.put('/api/avatars/me', { headers: { 'If-Match': current.revision, 'Idempotency-Key': `reset-${Date.now()}` }, data: { body: 'body-sd-neutral-v1', equipment: { hair: 'hair-001', top: 'top-001', bottom: 'bottom-001', shoes: 'shoes-001' } } });
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await page.getByRole('link', { name: '모듈형 아바타' }).click();
  await page.getByRole('link', { name: '런타임 옷장' }).click();
  await expect(page.getByRole('button', { name: '장착 저장', exact: true })).toBeEnabled();
  await expect(page.locator('.avatar-viewport')).toHaveAttribute('data-renderer', /webgpu|webgl-fallback/);
  const preview = page.locator('.avatar-preview');
  await expect(preview).toHaveAttribute('data-skeleton-id', /.+/);
  const skeleton = await preview.getAttribute('data-skeleton-id');
  await page.getByRole('button', { name: 'Run', exact: true }).click();
  await expect(preview).toHaveAttribute('data-animation', 'run');
  await page.getByRole('tab', { name: '상의', exact: true }).click();
  await page.getByRole('button', { name: /블루 재킷/ }).click();
  await expect(page.locator('[data-equipped-slot="top"]')).toHaveAttribute('data-asset-id', 'top-002');
  await expect(preview).toHaveAttribute('data-skeleton-id', skeleton!);
  await expect(preview).toHaveAttribute('data-animation', 'run');
  await page.route('**/api/avatars/assets/top-003/model?lod=0', route => route.abort());
  await page.getByRole('button', { name: /머스터드 니트/ }).click();
  await expect(page.getByRole('alert')).toBeVisible();
  await expect(page.locator('[data-equipped-slot="top"]')).toHaveAttribute('data-asset-id', 'top-002');
  await page.unroute('**/api/avatars/assets/top-003/model?lod=0');
  await page.getByRole('button', { name: /머스터드 니트/ }).click();
  await expect(page.locator('[data-equipped-slot="top"]')).toHaveAttribute('data-asset-id', 'top-003');
  await page.getByRole('tab', { name: '원피스', exact: true }).click();
  await page.locator('.piece').click();
  await expect(page.locator('[data-equipped-slot="top"]')).toHaveCount(0);
  await expect(page.locator('[data-equipped-slot="bottom"]')).toHaveCount(0);
  await expect(page.locator('[data-equipped-slot="onepiece"]')).toHaveCount(1);
  await page.getByRole('combobox', { name: '디테일' }).selectOption('1');
  await expect(preview).toHaveAttribute('data-lod', '1');
  for (const name of ['Idle', 'Walk', 'Run', 'Jump', 'Sit', 'Arms Up', 'Crouch']) {
    await page.getByRole('button', { name, exact: true }).click();
    await expect(page.getByRole('button', { name, exact: true })).toHaveAttribute('aria-pressed', 'true');
    const sampleStart = Number(await preview.getAttribute('data-mixer-time'));
    await expect.poll(async () => Number(await preview.getAttribute('data-mixer-time'))).toBeGreaterThan(sampleStart + .5);
    await page.screenshot({ path: `test-results/avatar-${name.replaceAll(' ', '-')}.png` });
  }
  await page.getByRole('button', { name: '장착 저장', exact: true }).click();
  await expect(page.getByRole('status')).toHaveText('장착 상태를 서버에 저장했습니다.');
  const saved = await request.get('/api/avatars/me').then(response => response.json());
  expect(saved.state.equipment.onepiece).toBe('onepiece-001');
  await page.reload();
  await expect(page.locator('[data-equipped-slot="onepiece"]')).toHaveCount(1);
  await expect(page.locator('[data-equipped-slot="top"]')).toHaveCount(0);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: 'test-results/avatar-mobile.png', fullPage: true });
  expect(errors).toEqual([]);
});

test('uncertain save reuses its receipt and reconnect restores without a second mutation', async ({ page, request }) => {
  await page.goto('/avatar.html?view=wardrobe');
  await expect(page.getByRole('button', { name: '장착 저장', exact: true })).toBeEnabled();
  await page.getByRole('tab', { name: '모자', exact: true }).click();
  await page.getByRole('button', { name: /로즈 베레모/ }).click();
  await expect(page.locator('[data-equipped-slot="hat"]')).toHaveAttribute('data-asset-id', 'hat-002');
  await page.route('**/api/avatars/me', async route => {
    if (route.request().method() !== 'PUT') return route.continue();
    await route.fetch(); // Server commits; simulate losing only the response.
    await route.abort();
  });
  await page.getByRole('button', { name: '장착 저장', exact: true }).click();
  await expect(page.getByRole('alert')).toBeVisible();
  const committed = await request.get('/api/avatars/me').then(response => response.json());
  await page.unroute('**/api/avatars/me');
  await page.reload();
  await expect(page.getByRole('button', { name: '저장 재시도', exact: true })).toBeEnabled();
  await page.getByRole('button', { name: '저장 재시도', exact: true }).click();
  await expect(page.getByRole('status')).toHaveText('장착 상태를 서버에 저장했습니다.');
  const replayed = await request.get('/api/avatars/me').then(response => response.json());
  expect(replayed).toEqual(committed);
  await page.route('**/api/avatars/me', route => route.abort());
  await page.getByRole('button', { name: '서버에서 불러오기' }).click();
  await expect(page.getByRole('alert')).toBeVisible();
  await expect(page.locator('[data-equipped-slot="hat"]')).toHaveAttribute('data-asset-id', 'hat-002');
  await page.unroute('**/api/avatars/me');
  await page.getByRole('button', { name: '서버에서 불러오기' }).click();
  await expect(page.getByRole('status')).toHaveText('서버의 장착 상태를 불러왔습니다.');
});

test('canonical runtime shares resources but isolates skeletons, masks and ID snapshots', async ({ page }) => {
  await page.goto('/avatar.html?view=wardrobe');
  await expect(page.getByRole('button', { name: /장착 저장|저장 재시도/ })).toBeEnabled();
  const result = await page.evaluate(async () => {
    const runtimePath = '/src/avatar/runtime/AvatarRuntime.ts';
    const cachePath = '/src/assets/GLTFAssetCache.ts';
    const manifestPath = '/src/avatar/core/manifest.ts';
    const { AvatarRuntime } = await import(runtimePath);
    const { GLTFAssetCache } = await import(cachePath);
    const { avatarManifestFromRecord } = await import(manifestPath);
    const { assets } = await fetch('/api/avatars/catalog').then(response => response.json());
    const cache = new GLTFAssetCache();
    const options = { cache, getAsset: (id: string) => assets.find((asset: { id: string }) => asset.id === id) };
    const a = new AvatarRuntime(options), b = new AvatarRuntime(options);
    const initial = { body: 'body-sd-neutral-v1', equipment: { top: 'top-001', bottom: 'bottom-001' } };
    try {
      await Promise.all([a.restore(initial), b.restore(initial)]);
      const meshes = (avatar: typeof a) => { const result: any[] = []; avatar.scene.traverse((object: any) => { if (object.isSkinnedMesh) result.push(object); }); return result; };
      const aMeshes = meshes(a), bMeshes = meshes(b);
      const skeletons = new Set(aMeshes.map(mesh => mesh.skeleton));
      const sharedGeometry = aMeshes[0].geometry === bMeshes[0].geometry;
      const independentSkeleton = aMeshes[0].skeleton !== bMeshes[0].skeleton;
      const source = avatarManifestFromRecord(options.getAsset(initial.body)).source.uri;
      const references = cache.getReferenceCount(source);
      const hiddenBefore = aMeshes.filter(mesh => !mesh.visible).length;
      a.playAnimation('walk'); a.update(.05);
      const animatedArm = aMeshes[0].skeleton.bones.find((bone: any) => bone.name === 'upperArmL');
      const restArm = bMeshes[0].skeleton.bones.find((bone: any) => bone.name === 'upperArmL');
      const independentAnimation = animatedArm.quaternion.angleTo(restArm.quaternion) > 0;
      const time = a.getDiagnostics().mixerTime;
      await a.equip('top', 'top-002');
      const sameTime = a.getDiagnostics().mixerTime === time;
      const before = JSON.stringify(a.getSnapshot());
      let failed = false;
      try { await a.equip('top', 'hair-001'); } catch { failed = true; }
      const rollback = before === JSON.stringify(a.getSnapshot());
      a.unequip('top');
      const hiddenAfter = meshes(a).filter(mesh => !mesh.visible).length;
      const immutable = Object.isFrozen(a.getSnapshot()) && Object.isFrozen(a.getSnapshot().equipment);
      a.dispose();
      const remaining = cache.getReferenceCount(source);
      b.update(.05);
      const bodyStillVisible = meshes(b).some(mesh => mesh.visible);
      return { skeletonCount: skeletons.size, bones: b.getDiagnostics().boneCount, sharedGeometry, independentSkeleton, independentAnimation, references, hiddenBefore, hiddenAfter, sameTime, failed, rollback, immutable, remaining, bodyStillVisible, snapshot: b.getState() };
    } finally { a.dispose(); b.dispose(); }
  });
  expect(result).toMatchObject({ skeletonCount: 1, bones: 23, sharedGeometry: true, independentSkeleton: true, independentAnimation: true, references: 2, sameTime: true, failed: true, rollback: true, immutable: true, remaining: 1, bodyStillVisible: true });
  expect(result.hiddenBefore).toBeGreaterThan(result.hiddenAfter);
  expect(result.hiddenAfter).toBeGreaterThan(0); // Bottom's mask survives top removal.
  expect(result.snapshot).toEqual({ body: 'body-sd-neutral-v1', equipment: { top: 'top-001', bottom: 'bottom-001' } });
});

test('studio shows live character results, implementation scope and reconnects after reload', async ({ page, request }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  const { characters } = await request.get('/api/characters').then(response => response.json());
  const source = characters.find((character: { model_id: string }) => character.model_id);
  await page.goto('/avatar.html?view=wardrobe');
  await expect(page.getByRole('button', { name: '장착 저장', exact: true })).toBeEnabled();
  await page.getByRole('button', { name: '구현 현황', exact: true }).click();
  await expect(page.locator('dialog')).toBeVisible();
  await expect(page.locator('.runtime-banner')).toContainText(/WebGPU 실행 중|WebGL 호환 모드 실행 중/);
  await expect(page.locator('.feature-list')).toContainText('23개 bone');
  await expect(page.locator('.next-connections')).toContainText('Tripo 생성 자동화');
  await page.screenshot({ path: 'test-results/studio-implementation.png' });
  await page.getByRole('button', { name: '구현 현황 닫기' }).click();
  await page.getByRole('button', { name: new RegExp(source.name) }).click();
  await expect(page.locator('.source-model-viewer')).toHaveAttribute('data-model-sha256', source.model_sha256);
  await expect(page.locator('.source-model-viewer')).toHaveAttribute('data-renderer', /webgpu|webgl-fallback/);
  await expect(page.getByRole('region', { name: '캐릭터 작업 상태' })).toContainText(source.name);
  await expect(page.locator('.scene-loading')).toHaveCount(0);
  await page.reload();
  await expect(page.locator('.source-model-viewer')).toHaveAttribute('data-model-sha256', source.model_sha256);
  await page.route('**/api/characters', route => route.abort());
  await page.getByRole('button', { name: '캐릭터 목록 새로고침' }).click();
  await expect(page.locator('.sidebar-error')).toBeVisible();
  await expect(page.getByRole('region', { name: '캐릭터 작업 상태' })).toContainText(source.name);
  await page.unroute('**/api/characters');
  await page.getByRole('button', { name: '캐릭터 목록 새로고침' }).click();
  await expect(page.locator('.sidebar-error')).toHaveCount(0);
  await page.getByRole('button', { name: '모듈형 아바타 선택' }).click();
  await expect(page.getByRole('region', { name: '파츠 선택' })).toBeVisible();
  await page.getByRole('button', { name: '시점 초기화' }).click();
  await page.screenshot({ path: 'test-results/studio-desktop.png' });
  expect(errors).toEqual([]);
});
