import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { chromium } from '@playwright/test';

const origin = process.argv[2] || 'http://127.0.0.1:5275';
const jobId = process.argv[3];
assert.match(jobId || '', /^[a-f0-9]{24}$/, 'Pass the native assembly job ID as the second argument.');
const output = path.resolve('../data/verification', `native-assembly-${Date.now()}`);
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ channel: process.env.WORKSPACE_TEST_BROWSER || 'chromium' });
const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
const errors = [], mutations = [];
page.on('pageerror', e => errors.push(e.message));
page.on('request', r => { if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(r.method())) mutations.push(r.url()); });
const delta = (a, b) => {
  assert(Array.isArray(a) && a.length > 0 && a.length === b.length, 'Vertex samples must have equal, nonzero lengths');
  assert([...a, ...b].every(Number.isFinite), 'Vertex samples must be finite');
  return Math.max(0, ...b.map((v, i) => Math.abs(v - a[i])));
};
try {
  const response = await page.request.get(`${origin}/api/avatar-factory/jobs/${jobId}`);
  assert(response.ok()); const job = await response.json();
  const assemblyResponse = await page.request.get(`${origin}/api/avatar-factory/jobs/${jobId}/native-parts`);
  assert(assemblyResponse.ok()); const assembly = await assemblyResponse.json();
  const slots = assembly.parts.filter(part => part.slot !== 'body').map(part => part.slot).sort();
  assert(slots.length > 0, 'The assembly must include wearable parts');
  const url = `${origin}/?character=${encodeURIComponent(job.character_id)}&job=${jobId}`;
  await page.goto(url);
  const panel = page.locator('.assembly-preview'), scene = panel.locator('.meshy-scene');
  await page.waitForFunction(() => !!document.querySelector('[data-assembly-ready]')?.getAttribute('data-assembly-ready'), undefined, { timeout: 90000 });
  await panel.getByRole('button', { name: '모두 착용', exact: true }).click();
  await page.waitForFunction(count => Object.keys(JSON.parse(document.querySelector('.assembly-preview')?.getAttribute('data-part-samples') || '{}')).length === count, slots.length);
  const samples = async () => ({
    body: JSON.parse(await panel.getAttribute('data-body-sample') || '[]'),
    parts: JSON.parse(await panel.getAttribute('data-part-samples') || '{}'),
  });
  const motions = {};
  for (const name of ['walk', 'run', 'jump', 'sit']) {
    await panel.getByRole('button', { name, exact: true }).click();
    await page.waitForTimeout(350);
    const before = await samples();
    await page.waitForTimeout(450);
    const after = await samples();
    motions[name] = { bodyDisplacement: delta(before.body, after.body), parts: Object.fromEntries(Object.entries(after.parts).map(([slot, points]) => [slot, delta(before.parts[slot], points)])) };
    assert.equal(await panel.getAttribute('data-shared-bones'), 'true');
    assert.deepEqual(Object.keys(after.parts).sort(), slots);
    assert(motions[name].bodyDisplacement > 1e-5, `${name}: body must move`);
    for (const [slot, displacement] of Object.entries(motions[name].parts)) {
      assert(displacement > 1e-5, `${name}: ${slot} must move with the body`);
    }
    await scene.screenshot({ path: path.join(output, `${name}.png`) });
  }
  await panel.getByRole('checkbox', { name: '모자', exact: true }).uncheck();
  await page.waitForFunction(() => !('hat' in JSON.parse(document.querySelector('.assembly-preview')?.getAttribute('data-part-samples') || '{}')));
  await panel.getByRole('checkbox', { name: '모자', exact: true }).check();
  await page.waitForFunction(() => 'hat' in JSON.parse(document.querySelector('.assembly-preview')?.getAttribute('data-part-samples') || '{}'));
  await panel.getByRole('button', { name: '조립 캐릭터로 이동', exact: true }).click();
  await page.waitForFunction(() => !!document.querySelector('[data-assembly-ready]')?.getAttribute('data-assembly-ready') && !!document.querySelector('[data-character-position]'));
  const position = async () => JSON.parse(await scene.getAttribute('data-character-position'));
  const from = await position();
  await scene.locator('canvas').click();
  await page.keyboard.down('w');
  try { await page.waitForTimeout(800); } finally { await page.keyboard.up('w'); }
  const to = await position();
  const distance = Math.hypot(to.x - from.x, to.z - from.z);
  assert(distance > .2);
  assert.equal(await panel.getAttribute('data-shared-bones'), 'true');
  assert.deepEqual(Object.keys((await samples()).parts).sort(), slots);
  await scene.screenshot({ path: path.join(output, 'world.png') });
  const version = await panel.getAttribute('data-assembly-ready');
  assert.equal(version, assembly.version);
  const report = { checkedAt: new Date().toISOString(), jobId, version, url,
    artifacts: assembly.artifacts.filter(a => a.name.endsWith('.glb')).map(({ name, sha256 }) => ({ name, sha256 })),
    renderer: await scene.getAttribute('data-renderer'), boneCount: Number(await panel.getAttribute('data-bone-count')),
    motions, world: { from, to, distance }, errors, mutations,
    limits: 'Existing generated assets. Movement and binding evidence; garment fit and visual approval remain separate.' };
  await writeFile(path.join(output, 'report.json'), JSON.stringify(report, null, 2));
  assert.deepEqual(errors, []); assert.deepEqual(mutations, []);
  console.log(JSON.stringify({ output, url, renderer: report.renderer, boneCount: report.boneCount, distance }));
} finally { await browser.close(); }
