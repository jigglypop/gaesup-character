import { test, expect, type Page } from '@playwright/test';

async function settled(page: Page) {
  await expect(page.locator('.operation b')).toHaveText('작업 완료');
}

test('real API settings, rig preview, parts and versioned review survive reload', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await expect(page.locator('.character-card')).toHaveCount(1);
  await expect(page.locator('#model-loading')).toHaveCount(0);
  await expect(page.locator('canvas')).toBeVisible();
  await page.getByRole('textbox', { name: '캐릭터 이름', exact: true }).fill('Browser Checked');
  await page.getByRole('spinbutton', { name: '캐릭터 키' }).fill('1.85');
  await page.getByRole('button', { name: '설정 저장' }).click();
  await expect(page.locator('#notice')).toHaveText('설정을 저장했습니다.');
  await page.reload();
  await expect(page.getByRole('spinbutton', { name: '캐릭터 키' })).toHaveValue('1.85');
  await page.locator('[data-action="inspect_model"]').click();
  await settled(page);
  await expect(page.locator('.quality-note')).toContainText('구조 검사 통과');
  await page.getByRole('combobox', { name: 'body 역할', exact: true }).selectOption('body');
  await page.getByRole('combobox', { name: 'outfit 역할', exact: true }).selectOption('outfit_base');
  await page.locator('[name="coverage"]').selectOption('partial');
  await page.getByRole('button', { name: '파츠 역할 저장' }).click();
  await expect(page.locator('.operation code')).toHaveText('organize_parts');
  await settled(page);
  await page.getByRole('checkbox', { name: 'outfit 표시' }).uncheck();
  await expect(page.getByRole('checkbox', { name: 'outfit 표시' })).not.toBeChecked();
  await page.locator('[name="notes"]').fill('브라우저 검증용 삼각형 모델. 실제 캐릭터 시각 승인이 아님.');
  await page.getByRole('button', { name: '수정 요청', exact: true }).click();
  await expect(page.locator('.operation code')).toHaveText('record_review');
  await settled(page);
  await page.reload();
  await expect(page.locator('[name="notes"]')).toHaveValue(/브라우저 검증용/);
  await expect(page.locator('#detail .badge')).toHaveText('검수 대기');
  await page.screenshot({ path: 'test-results/workspace-fixture.png', fullPage: true });
  expect(errors).toEqual([]);
});

test('lost action response restores same receipt after reload without a second execution', async ({ page, request }) => {
  const list = await (await request.get('/api/characters')).json();
  const id = list.characters[0].id;
  let lostId = '';
  await page.goto('/#' + id);
  await page.route('**/actions/inspect_model', async route => {
    const response = await route.fetch();
    lostId = (await response.json()).operation.id;
    await route.abort('failed');
  }, { times: 1 });
  await page.locator('[data-action="inspect_model"]').click();
  await expect(page.getByRole('button', { name: '요청 상태 복구' })).toBeVisible();
  await page.reload();
  await page.getByRole('button', { name: '요청 상태 복구' }).click();
  await expect(page.getByRole('button', { name: '요청 상태 복구' })).toHaveCount(0);
  const detail = await (await request.get('/api/characters/' + id)).json();
  expect(detail.operation.id).toBe(lostId);
  expect(detail.operation.status).toBe('succeeded');
});

test('registration, upload error and narrow viewport work with the real API', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await page.locator('#new-character').click();
  await page.locator('#create-dialog input[name="name"]').fill('Imported Character');
  await page.locator('#create-dialog [type="submit"]').click();
  await expect(page.locator('#detail h2')).toContainText('Imported Character');
  await page.locator('#model-file').setInputFiles({ name: 'invalid.glb', mimeType: 'model/gltf-binary', buffer: Buffer.from('bad') });
  await expect(page.locator('#notice')).toContainText('GLB 구조 검사');
  await page.reload();
  await expect(page.locator('#detail h2')).toContainText('Imported Character');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: 'test-results/workspace-mobile.png', fullPage: true });
});

test('painted source faces become a versioned Blender part through the real API', async ({ page, request }) => {
  test.setTimeout(90000);
  const errors: string[] = []; page.on('pageerror', error => errors.push(error.message));
  const list = await (await request.get('/api/characters')).json();
  const source = list.characters.find((c: { model_id: string }) => c.model_id);
  await page.goto('/#' + source.id);
  await expect(page.locator('#model-loading')).toHaveCount(0);
  await page.locator('#expand-world').click();
  await page.locator('#edit-parts').click();
  await page.locator('#paint-role').selectOption('hat');
  const canvas = page.locator('#viewer canvas');
  await expect(canvas).toBeVisible();
  // Camera framing completes on an actual rendered frame.
  await page.evaluate(() => new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
  const box = (await canvas.boundingBox())!;
  await page.mouse.click(box.x + box.width * .47, box.y + box.height * .54);
  await expect(page.locator('#split-painted')).toBeEnabled();
  const actionResponse = page.waitForResponse(response => response.url().endsWith('/actions/separate_parts') && response.request().method() === 'POST');
  await page.locator('#split-painted').click();
  const receipt = await (await actionResponse).json();
  await expect.poll(async () => (await (await request.get(`/api/characters/${source.id}/operations/${receipt.operation.id}`)).json()).status, { timeout: 60000 }).toBe('succeeded');
  const result = await (await request.get('/api/characters/' + source.id)).json();
  expect(result.model_sha256).not.toBe(source.model_sha256);
  expect(result.parts.some((part: { role: string }) => part.role === 'hat')).toBe(true);
  expect(result.artifacts.some((a: { id: string }) => a.id === 'parts_blend')).toBe(true);
  expect(result.inspection.errors).toEqual([]);
  expect(result.review.decision).not.toBe('approved');
  await page.reload();
  await expect(page.locator('#model-loading')).toHaveCount(0);
  await expect(page.getByRole('combobox', { name: /hat_.* 역할/ })).toHaveValue('hat');
  expect(errors).toEqual([]);
});
