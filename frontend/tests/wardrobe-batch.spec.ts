import { test, expect } from '@playwright/test';
import { createHash } from 'node:crypto';

test('unapproved body preview stays singular while live review state refreshes', async ({ page }) => {
  test.skip(process.env.WORKSPACE_TEST_MESHY !== '1', 'Requires isolated native skeleton fixture.');
  await page.goto(`/avatar.html?stage=standard&item=${'d'.repeat(24)}`);
  await expect(page.locator('[data-standard-preview]')).toHaveCount(1);
  await expect(page.locator('[data-standard-preview]')).toHaveAttribute('data-standard-ready', 'd'.repeat(24));
  await expect(page.locator('.standard-scene')).toHaveAttribute('data-renderer', /webgpu|webgl-fallback/);
  for (let i = 0; i < 3; i++) {
    const response = page.waitForResponse(r => r.url().endsWith('/api/avatar-standard/items'));
    await page.evaluate(() => window.dispatchEvent(new Event('online')));
    await response;
  }
  await expect(page.locator('[data-standard-preview]')).toHaveCount(1);
  await expect(page.getByRole('button', { name: '검수한 몸·골격 고정', exact: true })).toHaveCount(1);
  await page.reload();
  await expect(page.locator('[data-standard-preview]')).toHaveCount(1);
});

test('wardrobe batch edits multiple slots, shows exact request bounds, and reconnects to the real API', async ({ page, request }) => {
  await page.goto('/avatar.html?stage=standard');
  const panel = page.getByRole('region', { name: '의상 일괄 생산' });
  await expect(panel.getByRole('button', { name: '의상 2개 일괄 생산 시작' })).toBeDisabled();
  await panel.getByLabel('의상 1 이름', { exact: true }).fill('크림 반팔');
  await panel.getByLabel('의상 1 설명', { exact: true }).fill('크림색 둥근 목 반팔 티셔츠');
  await panel.getByLabel('의상 2 슬롯', { exact: true }).selectOption('bottom');
  await panel.getByLabel('의상 2 이름', { exact: true }).fill('분홍 반바지');
  await panel.getByLabel('의상 2 설명', { exact: true }).fill('분홍색 짧은 반바지, 장식 없음');
  await panel.getByRole('button', { name: '의상 추가', exact: true }).click();
  await expect(panel.getByText('총 3개 · Sunburst 시안 최대 3회 + Meshy 7 형상 최대 3회 · 의상별 추가 리깅 0회')).toBeVisible();
  await panel.getByRole('button', { name: '의상 3 삭제', exact: true }).click();
  await expect(panel.getByLabel('의상 2 슬롯', { exact: true })).toHaveValue('bottom');
  await page.route('**/api/avatar-standard/batches', route => route.abort());
  await page.evaluate(() => window.dispatchEvent(new Event('online')));
  await expect(panel.getByRole('alert')).toContainText('연결', { timeout: 10000 });
  await page.unroute('**/api/avatar-standard/batches');
  await page.evaluate(() => window.dispatchEvent(new Event('online')));
  await expect(panel.getByRole('alert')).toHaveCount(0, { timeout: 10000 });
  expect((await request.get('/api/avatar-standard/batches')).status()).toBe(200);
  const bad = await request.post('/api/avatar-standard/batches', { headers: { 'Idempotency-Key': 'browser-batch-invalid' },
    data: { name: 'invalid', base_id: '0'.repeat(24), base_sha256: '0'.repeat(64), rows: [], max_images_per_row: 2 } });
  expect(bad.status()).toBe(422);
  await page.reload();
  await expect(panel.getByRole('heading', { name: '같은 몸에 갈아입힐 의상 일괄 생산' })).toBeVisible();
  await expect(panel.getByLabel('의상 1 이름', { exact: true })).toHaveValue('크림 반팔');
  await expect(panel.getByLabel('의상 2 슬롯', { exact: true })).toHaveValue('bottom');
});

test('batch captures the chosen character image and sends its exact hash for every garment', async ({ page, request }) => {
  test.skip(!process.env.WORKSPACE_TEST_STANDARD_ROOT, 'Requires the disposable standard base.');
  const { items } = await request.get('/api/avatar-standard/items').then(r => r.json());
  const base = items.find((item: any) => item.kind === 'base' && item.status === 'approved');
  const source = await request.get(base.artifacts.find((a: any) => a.name === 'front.png').url).then(r => r.body());
  const character = await request.post('/api/characters', { data: { name: 'Reference image fixture', height_meters: 1.2 } }).then(r => r.json());
  const uploaded = await request.post(`/api/characters/${character.id}/sources?kind=image`, {
    headers: { 'Content-Type': 'image/png', 'If-Match': character.revision }, data: source,
  });
  expect(uploaded.status()).toBe(200);
  let payload: any;
  page.on('request', r => { if (r.method() === 'POST' && r.url().endsWith('/api/avatar-standard/batches')) payload = r.postDataJSON(); });
  await page.goto(`/avatar.html?stage=standard&character=${character.id}`);
  const panel = page.getByRole('region', { name: '의상 일괄 생산' });
  await expect(panel.getByLabel('배치 참고 원본')).toHaveValue(character.id);
  await expect(panel.getByAltText('Reference image fixture 배치 참고 원본')).toBeVisible();
  await panel.getByLabel('의상 1 설명', { exact: true }).fill('참고 이미지의 크림색 반팔 티셔츠');
  await panel.getByLabel('의상 2 설명', { exact: true }).fill('참고 이미지 색상에 맞춘 분홍 카디건');
  await panel.getByRole('button', { name: '의상 2개 일괄 생산 시작' }).click();
  await expect(panel.getByRole('alert')).toContainText('OpenAI와 Meshy 설정');
  expect(payload.reference_asset).toBe(createHash('sha256').update(source).digest('hex'));
  expect(payload.base_id).toBe(base.id);
  expect(payload.rows).toHaveLength(2);
  expect((await request.get('/api/avatar-standard/batches').then(r => r.json())).items).toHaveLength(0);
  await page.reload();
  await expect(panel.getByLabel('배치 참고 원본')).toHaveValue(character.id);
  await expect(panel.getByAltText('Reference image fixture 배치 참고 원본')).toBeVisible();
});
