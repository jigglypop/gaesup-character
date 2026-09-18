import { expect, test } from '@playwright/test';

test('assembled parts animate, change together, restore after lost save and move through the world', async ({ page, request }) => {
  test.skip(process.env.WORKSPACE_TEST_NATIVE !== '1', 'Requires isolated assembly fixture.');
  test.setTimeout(180000);
  const id = 'e'.repeat(24), version = 'f'.repeat(24);
  const listing = await request.get('/api/avatar-factory/jobs').then(r => r.json());
  const job = listing.jobs.find((j: { id: string }) => j.id === id);
  const errors: string[] = [], posts: string[] = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('request', r => { if (r.method() === 'POST') posts.push(r.url()); });
  await page.goto(`/avatar.html?stage=glb&character=${job.character_id}&job=${id}&tab=result`);
  const panel = page.locator('.assembly-preview'), scene = panel.locator('.meshy-scene');
  await expect(panel).toHaveAttribute('data-assembly-ready', version, { timeout: 90000 });
  await expect(panel).toHaveAttribute('data-shared-bones', 'true');
  await expect(scene).toHaveAttribute('data-renderer', /webgpu|webgl-fallback/);
  await expect(panel.getByRole('button', { name: 'walk', exact: true })).toHaveAttribute('aria-pressed', 'true');
  const samples = () => panel.getAttribute('data-part-samples').then(value => JSON.parse(value || '{}') as Record<string, number[]>);
  const before = await samples();
  expect(Object.keys(before)).toHaveLength(6);
  for (const slot of Object.keys(before)) {
    await expect.poll(async () => {
      const after = (await samples())[slot] || [];
      return Math.max(0, ...after.map((v, i) => Math.abs(v - before[slot][i])));
    }).toBeGreaterThan(1e-5);
  }
  await panel.getByRole('checkbox', { name: '모자', exact: true }).uncheck();
  await expect.poll(async () => Object.keys(await samples())).not.toContain('hat');
  await expect(panel.getByRole('button', { name: 'walk', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await panel.getByRole('button', { name: 'run', exact: true }).click();
  await expect(panel.getByRole('button', { name: 'run', exact: true })).toHaveAttribute('aria-pressed', 'true');
  let lost = true;
  await page.route(`**/api/avatar-factory/jobs/${id}/native-outfits/${version}`, async route => {
    if (route.request().method() === 'PUT' && lost) { lost = false; await route.fetch(); await route.abort(); }
    else await route.continue();
  });
  await panel.getByRole('button', { name: '현재 조합 저장', exact: true }).click();
  await expect(panel.getByRole('button', { name: '조합 저장 결과 복구' })).toBeEnabled();
  await page.reload();
  await expect(panel).toHaveAttribute('data-assembly-ready', version, { timeout: 90000 });
  await expect(panel.getByRole('checkbox', { name: '모자', exact: true })).not.toBeChecked();
  await panel.getByRole('button', { name: '조합 저장 결과 복구' }).click();
  await expect(panel.getByText('저장된 조합입니다.', { exact: true })).toBeVisible();
  const saved = await request.get(`/api/avatar-factory/jobs/${id}/native-outfits/${version}`).then(r => r.json());
  expect(saved.slots).not.toContain('hat'); expect(saved.slots).toHaveLength(5);
  await panel.getByRole('button', { name: '조립 캐릭터로 이동', exact: true }).click();
  await expect(panel).toHaveAttribute('data-assembly-ready', version, { timeout: 90000 });
  await expect(scene).toHaveAttribute('data-world', 'gaesup-world');
  const position = () => scene.getAttribute('data-character-position').then(v => JSON.parse(v || '{}'));
  const origin = await position();
  await scene.locator('canvas').click();
  await page.keyboard.down('w');
  try {
    await expect.poll(async () => { const p = await position(); return Math.hypot(p.x - origin.x, p.z - origin.z); }).toBeGreaterThan(.2);
  } finally { await page.keyboard.up('w'); }
  await expect(panel).toHaveAttribute('data-shared-bones', 'true');
  expect(Object.keys(await samples())).toHaveLength(5);
  expect(errors).toEqual([]); expect(posts).toEqual([]);
  await page.screenshot({ path: 'test-results/native-assembly-world.png', fullPage: true });
});

test('recovering a lost save restores the newer combination saved in another tab', async ({ page, request }) => {
  test.skip(process.env.WORKSPACE_TEST_NATIVE !== '1', 'Requires isolated assembly fixture.');
  test.setTimeout(180000);
  const id = 'e'.repeat(24), version = 'f'.repeat(24);
  const endpoint = `/api/avatar-factory/jobs/${id}/native-outfits/${version}`;
  const job = await request.get(`/api/avatar-factory/jobs/${id}`).then(r => r.json());
  const errors: string[] = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.goto(`/?character=${job.character_id}&job=${id}`);
  const panel = page.locator('.assembly-preview');
  await expect(panel).toHaveAttribute('data-assembly-ready', version, { timeout: 90000 });
  await panel.getByRole('button', { name: '모두 착용', exact: true }).click();
  await expect.poll(async () => Object.keys(JSON.parse(await panel.getAttribute('data-part-samples') || '{}')).length).toBe(6);
  // A lost response leaves a receipt for the old save. A second writer then
  // commits a newer combination before the first tab recovers that receipt.
  let lost = true;
  await page.route(`**${endpoint}`, async route => {
    if (route.request().method() === 'PUT' && lost) {
      lost = false; await route.fetch(); await route.abort();
    } else await route.continue();
  });
  await panel.getByRole('button', { name: '현재 조합 저장', exact: true }).click();
  await expect(panel.getByRole('button', { name: '조합 저장 결과 복구' })).toBeEnabled();
  const previous = await request.get(endpoint).then(r => r.json());
  const response = await request.put(endpoint, {
    headers: { 'If-Match': previous.revision, 'Idempotency-Key': `second-tab-${Date.now()}` },
    data: { body_sha256: previous.body_sha256, slots: ['top', 'shoes'] },
  });
  expect(response.ok()).toBe(true);
  const latest = await response.json();
  await page.reload();
  await expect(panel).toHaveAttribute('data-assembly-ready', version, { timeout: 90000 });
  await panel.getByRole('button', { name: '조합 저장 결과 복구' }).click();
  await expect(panel.getByText('저장된 조합입니다.', { exact: true })).toBeVisible();
  await expect(panel.getByRole('checkbox', { name: '모자', exact: true })).not.toBeChecked();
  await expect.poll(async () => Object.keys(JSON.parse(await panel.getAttribute('data-part-samples') || '{}')).sort()).toEqual(['shoes', 'top']);
  expect(await request.get(endpoint).then(r => r.json())).toEqual(latest);
  expect(errors).toEqual([]);
});
