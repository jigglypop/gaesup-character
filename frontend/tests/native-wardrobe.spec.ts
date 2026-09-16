import { createHash } from 'node:crypto';

import { expect, test } from '@playwright/test';


test('native parts share the 24-bone body, deform, and swap atomically without resetting motion', async ({ page, request }) => {
  test.skip(!process.env.WORKSPACE_TEST_STANDARD_ROOT, 'Requires the disposable real-Blender fixture.');

  const response = await request.get('/api/avatar-standard/items');
  expect(response.ok()).toBe(true);
  const { items } = await response.json();
  const base = items.find((item: any) => item.kind === 'base' && item.status === 'approved');
  const top = items.find((item: any) => item.kind === 'part' && item.contract.slot === 'top');
  const hat = items.find((item: any) => item.kind === 'part' && item.contract.slot === 'hat');
  expect(base).toBeTruthy(); expect(top).toBeTruthy(); expect(hat).toBeTruthy();

  const artifact = (item: any, name: string) => item.artifacts.find((value: any) => value.name === name);
  const baseModel = artifact(base, 'model.glb');
  const topModel = artifact(top, 'part.glb');
  const hatModel = artifact(hat, 'part.glb');
  for (const model of [baseModel, topModel, hatModel]) {
    expect(model.url).toMatch(/^\/api\/avatar-standard\/items\/[a-f0-9]{24}\/artifacts\/(model|part)\.glb$/);
    expect(model.sha256).toMatch(/^[a-f0-9]{64}$/);
  }

  const source = Buffer.from(await request.get(topModel.url).then(value => value.body()));
  const broken = Buffer.from(source);
  const before = Buffer.from('fixtureExtra');
  const after = Buffer.from('fixtureOther');
  let offset = 0, substitutions = 0;
  while ((offset = broken.indexOf(before, offset)) !== -1) {
    after.copy(broken, offset); offset += after.length; substitutions++;
  }
  expect(substitutions).toBeGreaterThan(0);
  const brokenSha256 = createHash('sha256').update(broken).digest('hex');

  await page.route('**/broken-skeleton.glb', route => route.fulfill({
    status: 200, contentType: 'model/gltf-binary', body: broken,
  }));
  await page.route('**/*slow-native=1', async route => {
    await new Promise(resolve => setTimeout(resolve, 250));
    await route.continue();
  });
  await page.goto('/avatar.html');

  const result = await page.evaluate(async ({ baseModel, topModel, hatModel, brokenSha256 }) => {
    const THREE = await import('/node_modules/three/build/three.module.js');
    const { GLTFLoader } = await import('/node_modules/three/examples/jsm/loaders/GLTFLoader.js');
    const { NativeWardrobe } = await import('/src/native-wardrobe.ts');
    const gltf = await new GLTFLoader().loadAsync(baseModel.url);
    const wardrobe = new NativeWardrobe(gltf.scene);
    const top = { id: 'fixture-top', slot: 'top', url: topModel.url, sha256: topModel.sha256 };
    const hat = { id: 'fixture-hat', slot: 'hat', url: hatModel.url, sha256: hatModel.sha256 };
    const mixer = new THREE.AnimationMixer(gltf.scene);
    const clip = gltf.animations.find((value: any) => value.name === 'walk');
    if (!clip) throw new Error('Fixture walk animation missing');
    mixer.clipAction(clip).play();

    if (!await wardrobe.equip([top])) throw new Error('Initial top did not commit');
    const initial = wardrobe.diagnostics();
    const sampleBefore = initial.sample;
    mixer.update(.23);
    const sampleAfter = wardrobe.diagnostics().sample;
    const maxDeformation = Math.max(...sampleAfter.map((value: number, index: number) => Math.abs(value - sampleBefore[index])));

    const failures: string[] = [];
    const reject = async (part: any) => {
      try { await wardrobe.equip([part]); return 'accepted'; }
      catch (error) { failures.push(error instanceof Error ? error.message : String(error)); return 'rejected'; }
    };
    const wrongSha = await reject({ ...top, id: 'bad-sha', sha256: '0'.repeat(64) });
    const afterWrongSha = wardrobe.diagnostics().partIds;
    const wrongSlot = await reject({ ...top, id: 'bad-slot', slot: 'hat' });
    const afterWrongSlot = wardrobe.diagnostics().partIds;
    const wrongSkeleton = await reject({ id: 'bad-skeleton', slot: 'top', url: '/broken-skeleton.glb', sha256: brokenSha256 });
    const afterWrongSkeleton = wardrobe.diagnostics().partIds;

    const timeBeforeReplace = mixer.time;
    // A second version of the same slot must replace the original mesh, even
    // when both versions happen to use identical fixture geometry.
    const replaced = await wardrobe.equip([{ ...top, id: 'fixture-top-v2' }]);
    const afterReplace = wardrobe.diagnostics();
    const attachedIds: string[] = [];
    gltf.scene.traverse((node: any) => { if (node.userData.wardrobePartId) attachedIds.push(node.userData.wardrobePartId); });
    const timeAfterReplace = mixer.time;
    const timeBeforeUnequip = mixer.time;
    const unequipped = await wardrobe.equip([]);
    const timeAfterUnequip = mixer.time;

    const slow = wardrobe.equip([{ ...top, id: 'slow-top', url: `${top.url}?slow-native=1` }]);
    const fast = wardrobe.equip([{ ...hat, id: 'fast-hat' }]);
    const [slowCommitted, fastCommitted] = await Promise.all([slow, fast]);
    const latest = wardrobe.diagnostics();

    mixer.stopAllAction(); mixer.uncacheRoot(gltf.scene); wardrobe.dispose();
    return {
      boneCount: initial.boneCount,
      shared: initial.shared,
      maxDeformation,
      wrongSha, wrongSlot, wrongSkeleton, failures,
      afterWrongSha, afterWrongSlot, afterWrongSkeleton,
      replaced, afterReplace, attachedIds, unequipped, timeBeforeReplace, timeAfterReplace, timeBeforeUnequip, timeAfterUnequip,
      slowCommitted, fastCommitted, latest,
    };
  }, { baseModel, topModel, hatModel, brokenSha256 });

  expect(result.boneCount).toBe(24);
  expect(result.shared).toBe(true);
  expect(result.maxDeformation).toBeGreaterThan(1e-4);
  expect([result.wrongSha, result.wrongSlot, result.wrongSkeleton]).toEqual(['rejected', 'rejected', 'rejected']);
  expect(result.failures[0]).toContain('검수한 버전');
  expect(result.failures[1]).toContain('해당 슬롯');
  expect(result.failures[2]).toContain('본 위치·구조');
  expect(result.afterWrongSha).toEqual(['fixture-top']);
  expect(result.afterWrongSlot).toEqual(['fixture-top']);
  expect(result.afterWrongSkeleton).toEqual(['fixture-top']);
  expect(result.replaced).toBe(true); expect(result.unequipped).toBe(true);
  expect(result.afterReplace.partIds).toEqual(['fixture-top-v2']);
  expect(result.afterReplace.shared).toBe(true);
  expect(result.attachedIds.length).toBeGreaterThan(0);
  expect(result.attachedIds.every(id => id === 'fixture-top-v2')).toBe(true);
  expect(result.timeAfterReplace).toBe(result.timeBeforeReplace);
  expect(result.timeAfterUnequip).toBe(result.timeBeforeUnequip);
  expect(result.slowCommitted).toBe(false);
  expect(result.fastCommitted).toBe(true);
  expect(result.latest.partIds).toEqual(['fast-hat']);
  expect(result.latest.shared).toBe(true);
});
