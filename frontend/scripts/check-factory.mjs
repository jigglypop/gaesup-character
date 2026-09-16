import { chromium, expect } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

const [jobId, address = 'http://127.0.0.1:5273'] = process.argv.slice(2);
if (!/^[a-f0-9]{24}$/.test(jobId || '')) throw new Error('Pass an existing factory job ID');
const base = new URL(address);
if (!['127.0.0.1', 'localhost', '[::1]'].includes(base.hostname)) throw new Error('Local API required');
const output = path.resolve('test-results', 'factory-' + jobId + '-' + Date.now());
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ channel: 'chrome', headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1600, height: 1100 } });
  const errors = [], mutations = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/*', async route => {
    if (!['GET', 'HEAD', 'OPTIONS'].includes(route.request().method())) {
      mutations.push(route.request().method() + ' ' + new URL(route.request().url()).pathname);
      await route.abort(); return;
    }
    await route.continue();
  });
  await page.goto(new URL('/avatar.html?stage=glb&character=A&job=' + jobId + '&tab=result', base).href);
  await expect(page.locator('[data-factory-ready="' + jobId + '"]')).toBeVisible({ timeout: 90000 });
  const backend = await page.locator('.avatar-viewport').getAttribute('data-renderer');
  await page.screenshot({ path: path.join(output, 'rest.png'), fullPage: true });
  await page.getByRole('button', { name: 'walk', exact: true }).click();
  await expect(page.getByRole('button', { name: 'walk', exact: true })).toHaveAttribute('aria-pressed', 'true');
  const runtime = await page.evaluate(async id => {
    const { AvatarRuntime } = await import('/src/avatar/runtime/AvatarRuntime.ts');
    const [catalog, job] = await Promise.all([
      fetch('/api/avatars/catalog').then(r => r.json()),
      fetch('/api/avatar-factory/jobs/' + id).then(r => r.json()),
    ]);
    const records = new Map(catalog.assets.map(asset => [asset.id, asset]));
    const avatar = new AvatarRuntime({ avatarId: 'production-verification', getAsset: key => records.get(key) });
    try {
      await avatar.restore(job.outfit);
      const before = avatar.getDiagnostics();
      const clips = avatar.getAnimationNames();
      const motion = {};
      for (const name of ['idle', 'walk', 'run', 'jump', 'sit', 'armsUp', 'crouch']) {
        avatar.playAnimation(name);
        avatar.update(.01);
        const sample = () => {
          const values = [];
          avatar.scene.traverse(node => { if (node.isBone) values.push(...node.position.toArray(), ...node.quaternion.toArray()); });
          return values;
        };
        const start = sample();
        let delta = 0;
        for (let frame = 0; frame < 12; frame++) {
          avatar.update(.05);
          sample().forEach((value, index) => { delta = Math.max(delta, Math.abs(value - start[index])); });
        }
        motion[name] = delta;
      }
      const swaps = [];
      for (const [slot, asset] of Object.entries(job.outfit.equipment)) {
        avatar.unequip(slot);
        if (avatar.getEquipment()[slot]) throw new Error('Part did not detach: ' + slot);
        await avatar.equip(slot, asset);
        if (avatar.getEquipment()[slot] !== asset) throw new Error('Part did not reattach: ' + slot);
        if (avatar.getDiagnostics().skeletonId !== before.skeletonId) throw new Error('Skeleton replaced by equipment swap');
        swaps.push(slot);
      }
      const skeletons = new Set();
      avatar.scene.traverse(node => { if (node.isSkinnedMesh) skeletons.add(node.skeleton.uuid); });
      return { rig: avatar.rig, wholeBody: records.get(job.outfit.body)?.metadata?.avatar?.wholeBody === true,
        boneCount: before.boneCount, clips, motion, swaps, sharedSkeletons: skeletons.size };
    } finally { avatar.dispose(); }
  }, jobId);
  expect(runtime.boneCount).toBe(23);
  expect(runtime.sharedSkeletons).toBe(1);
  expect(runtime.motion.walk).toBeGreaterThan(0);
  expect(runtime.motion.run).toBeGreaterThan(0);
  if (runtime.wholeBody) {
    expect(runtime.swaps).toEqual([]);
    await expect(page.locator('.factory-swaps')).toHaveCount(0);
    await expect(page.locator('.factory-stages')).not.toContainText('의상·파츠 분리');
    await expect(page.getByRole('heading', { name: '머리 포함 통짜 전신 모델' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'generated-body.glb', exact: true })).toBeVisible();
  } else expect(runtime.swaps).toEqual(expect.arrayContaining(['face', 'hair', 'hat', 'top', 'bottom', 'shoes']));
  await page.screenshot({ path: path.join(output, 'walk.png'), fullPage: true });
  if (runtime.wholeBody) {
    await page.getByRole('button', { name: '전신 시안', exact: true }).click();
    await expect(page.locator('.factory-workspace > img')).toBeVisible();
    await expect.poll(() => page.locator('.factory-workspace > img').evaluate(img => img.naturalWidth)).toBeGreaterThan(0);
    await page.getByRole('button', { name: '전신 결과 · 동작 확인', exact: true }).click();
    await expect(page.locator('[data-factory-ready="' + jobId + '"]')).toBeVisible({ timeout: 90000 });
  }
  await page.reload();
  await expect(page.locator('[data-factory-ready="' + jobId + '"]')).toBeVisible({ timeout: 90000 });
  const result = { jobId, url: page.url(), backend, runtime, reload: true, errors, mutations, output };
  await writeFile(path.join(output, 'result.json'), JSON.stringify(result, null, 2));
  console.log(JSON.stringify(result));
  expect(errors).toEqual([]);
  expect(mutations).toEqual([]);
} finally { await browser.close(); }
