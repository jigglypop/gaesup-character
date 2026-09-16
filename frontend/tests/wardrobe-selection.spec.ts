import { test, expect, type APIRequestContext } from '@playwright/test';

async function fixture(request: APIRequestContext) {
  const { items } = await request.get('/api/avatar-standard/items').then(r => r.json());
  const base = items.find((i: any) => i.kind === 'base' && i.status === 'approved');
  const parts = items.filter((i: any) => i.kind === 'part' && i.contract.base_id === base.id);
  const endpoint = `/api/avatar-standard/outfits/${base.id}`;
  const current = await request.get(endpoint).then(r => r.json());
  const response = await request.put(endpoint, { headers: { 'If-Match': current.revision, 'Idempotency-Key': crypto.randomUUID() },
    data: { base_sha256: base.model_sha256, part_ids: [] } });
  expect(response.status()).toBe(200);
  return { base, endpoint, top: parts.find((p: any) => p.contract.slot === 'top'), hat: parts.find((p: any) => p.contract.slot === 'hat') };
}

test.beforeEach(() => test.skip(!process.env.WORKSPACE_TEST_STANDARD_ROOT, 'Requires disposable Blender 24-bone fixture.'));

for (const interruption of ['connection', 'truncated-json']) test(`instant wardrobe keeps native bones moving and restores ${interruption} save response across reload`, async ({ page, request }) => {
  const { base, top, hat, endpoint } = await fixture(request);
  let bodyLoads = 0;
  const model = base.artifacts.find((a: any) => a.name === 'model.glb').url;
  page.on('request', request => { if (new URL(request.url()).pathname === model) bodyLoads++; });
  await page.goto('/avatar.html?stage=standard');
  const panel = page.locator('[data-wardrobe-preview]');
  await expect(panel).toHaveAttribute('data-wardrobe-ready', base.id);
  await panel.getByLabel('착용 상의', { exact: true }).selectOption(top.id);
  await expect(panel).toHaveAttribute('data-part-ids', JSON.stringify([top.id]));
  await panel.getByLabel('옷장 동작').selectOption({ label: 'walk' });
  const before = await panel.getAttribute('data-part-sample');
  await expect.poll(() => panel.getAttribute('data-part-sample')).not.toBe(before);
  await panel.getByLabel('착용 모자', { exact: true }).selectOption(hat.id);
  await expect(panel).toHaveAttribute('data-part-ids', JSON.stringify([top.id, hat.id]));
  await expect(panel).toHaveAttribute('data-shared-bones', 'true');
  await expect(panel).toHaveAttribute('data-bone-count', '24');
  await panel.getByLabel('착용 모자', { exact: true }).selectOption('');
  await expect(panel).toHaveAttribute('data-part-ids', JSON.stringify([top.id]));
  expect(bodyLoads).toBe(1);
  await expect(panel.getByLabel('옷장 동작')).not.toHaveValue('-1');

  const writes: { key: string; revision: string; body: string }[] = [];
  let committed: any;
  await page.route(`**${endpoint}`, async route => {
    if (route.request().method() !== 'PUT') return route.continue();
    const headers = route.request().headers();
    writes.push({ key: headers['idempotency-key'], revision: headers['if-match'], body: route.request().postData()! });
    const response = await route.fetch();
    committed = await response.json();
    if (writes.length === 1) {
      if (interruption === 'connection') await route.abort();
      else await route.fulfill({ status: 200, contentType: 'application/json', body: '{"revision":' });
    }
    else await route.fulfill({ response });
  });
  await panel.getByRole('button', { name: '현재 착용 저장', exact: true }).click();
  await expect(panel.getByRole('button', { name: '착용 저장 결과 복구' })).toBeEnabled();
  if (interruption === 'truncated-json') await expect(panel.getByRole('alert')).toContainText('응답을 끝까지 받지 못했습니다');
  expect(committed.part_ids).toEqual([top.id]);
  const revision = committed.revision;
  await page.reload();
  await expect(panel).toHaveAttribute('data-part-ids', JSON.stringify([top.id]));
  await expect(panel.getByLabel('착용 상의', { exact: true })).toBeDisabled();
  await panel.getByRole('button', { name: '착용 저장 결과 복구' }).click();
  await expect(panel.getByRole('button', { name: '현재 착용 저장', exact: true })).toBeDisabled();
  await expect(panel.getByRole('alert')).toHaveCount(0);
  expect(writes).toHaveLength(2); expect(writes[1]).toEqual(writes[0]);
  expect(committed.revision).toBe(revision);
  await page.reload();
  await expect(panel).toHaveAttribute('data-part-ids', JSON.stringify([top.id]));
  expect(writes).toHaveLength(2);
  expect((await request.get(endpoint).then(r => r.json())).part_ids).toEqual([top.id]);
  await expect(panel.locator('.wardrobe-scene')).toHaveAttribute('data-renderer', /webgpu|webgl-fallback/);
  await expect(panel.locator('.renderer-badge')).toBeVisible();
  await expect(panel.locator('.renderer-badge')).toHaveText((await panel.locator('.wardrobe-scene').getAttribute('data-renderer')) === 'webgpu' ? 'WebGPU · gaesup-world' : 'WebGL 호환 모드 · gaesup-world');
  console.log(`Native wardrobe renderer: ${await panel.locator('.wardrobe-scene').getAttribute('data-renderer')}`);
  await panel.screenshot({ path: 'test-results/native-wardrobe-saved.png' });
});

test('failed garment download and revision conflict keep current clothes until explicit restore', async ({ page, request }) => {
  const { base, top, hat, endpoint } = await fixture(request);
  await page.goto('/avatar.html?stage=standard');
  const panel = page.locator('[data-wardrobe-preview]');
  await expect(panel).toHaveAttribute('data-wardrobe-ready', base.id);
  await panel.getByLabel('착용 상의', { exact: true }).selectOption(top.id);
  await expect(panel).toHaveAttribute('data-part-ids', JSON.stringify([top.id]));
  const hatPath = `**${hat.artifacts.find((a: any) => a.name === 'part.glb').url}`;
  await page.route(hatPath, route => route.abort());
  await panel.getByLabel('착용 모자', { exact: true }).selectOption(hat.id);
  await expect(panel.getByRole('alert')).toContainText('기존 착용을 유지');
  await expect(panel).toHaveAttribute('data-part-ids', JSON.stringify([top.id]));
  await expect(panel.getByLabel('착용 모자', { exact: true })).toHaveValue('');
  await page.unroute(hatPath);
  await panel.getByLabel('착용 모자', { exact: true }).selectOption(hat.id);
  await expect(panel).toHaveAttribute('data-part-ids', JSON.stringify([top.id, hat.id]));
  const current = await request.get(endpoint).then(r => r.json());
  expect((await request.put(endpoint, { headers: { 'If-Match': current.revision, 'Idempotency-Key': crypto.randomUUID() },
    data: { base_sha256: base.model_sha256, part_ids: [hat.id] } })).status()).toBe(200);
  await panel.getByRole('button', { name: '현재 착용 저장', exact: true }).click();
  await expect(panel.getByRole('alert')).toContainText('최신 선택');
  await expect(panel).toHaveAttribute('data-part-ids', JSON.stringify([top.id, hat.id]));
  await panel.getByRole('button', { name: '저장한 착용 다시 불러오기', exact: true }).click();
  await expect(panel).toHaveAttribute('data-part-ids', JSON.stringify([hat.id]));
  await expect(panel.getByRole('alert')).toHaveCount(0);
  await page.route(`**${endpoint}`, route => route.abort());
  await page.reload();
  await expect(panel.getByRole('alert')).toContainText('연결');
  await expect(panel.getByLabel('착용 모자', { exact: true })).toBeDisabled();
  await page.unroute(`**${endpoint}`);
  await panel.getByRole('button', { name: '저장한 착용 다시 불러오기', exact: true }).click();
  await expect(panel).toHaveAttribute('data-part-ids', JSON.stringify([hat.id]));
});
