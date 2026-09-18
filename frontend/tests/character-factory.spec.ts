import { expect, test } from '@playwright/test';

test('old screen links all open the single photo-to-character screen', async ({ page }) => {
  for (const url of ['/', '/avatar.html?stage=standard', '/avatar.html?stage=glb', '/avatar.html?view=wardrobe']) {
    await page.goto(url);
    await expect(page.getByRole('heading', { name: '사진으로 캐릭터 만들기', exact: true })).toBeVisible();
    expect(new URL(page.url()).pathname).toBe('/');
    expect(new URL(page.url()).searchParams.has('stage')).toBe(false);
    expect(new URL(page.url()).searchParams.has('view')).toBe(false);
    await expect(page.getByRole('link', { name: /고정 몸|런타임 옷장|GLB 변환/ })).toHaveCount(0);
    await expect(page.getByRole('button', { name: '파츠 조립 · 로컬 처리' })).toHaveCount(0);
  }
});

test('one uploaded photo and one create button submit the full parts-and-rig job', async ({ page }) => {
  await page.route('**/api/avatar-factory/capabilities', route => route.fulfill({ json: {
    character_pipeline: 'parts_to_character_v1', ready: true, image_configured: true, meshy_configured: true, blender_available: true,
    image_provider: 'openai', image_model: 'gpt-image-2.5-sunburst', meshy_model: 'meshy-7', slots: [],
    next_actions: [{ id: 'produce_images', enabled: true }],
  } }));
  let submitted: any;
  await page.route('**/api/avatar-factory/image-jobs', async route => {
    submitted = route.request().postDataJSON();
    await route.fulfill({ status: 202, json: { id: 'a'.repeat(24), character_id: submitted.character_id,
      character_name: 'Photo fixture', production_mode: 'character_parts', input_kind: 'image', status: 'pipeline_queued',
      created_at: new Date().toISOString(), artifacts: [], parts: [], progress: { stage: 'images', message: '캐릭터 만드는 중' } } });
  });
  await page.goto('/');
  await page.getByLabel('캐릭터 사진', { exact: true }).setInputFiles({ name: 'photo.png', mimeType: 'image/png',
    buffer: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAIAAABLbSncAAAAFElEQVR4nGPcUpHCgA0wYRUdtBIAPMcBoH2gwicAAAAASUVORK5CYII=', 'base64') });
  await expect(page.getByAltText('캐릭터 원본 사진')).toBeVisible();
  await page.getByRole('button', { name: '캐릭터 만들기', exact: true }).click();
  await expect.poll(() => submitted).toBeTruthy();
  expect(submitted.production_mode).toBe('character_parts');
  expect(submitted.slots).toEqual(['body', 'hairBack', 'hairFront', 'hat', 'top', 'bottom', 'shoes']);
  expect(submitted.rig_with_meshy).toBe(true);
  expect(submitted.body_purpose).toBe('wardrobe_base');
  expect(new URL(page.url()).pathname).toBe('/');
  await expect(page.getByRole('heading', { name: '사진으로 캐릭터 만들기', exact: true })).toBeVisible();
});
