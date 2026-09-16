import { test, expect } from '@playwright/test';

test('whole character loads as one body and restores without separate clothes', async ({ page, request }) => {
  test.skip(!process.env.WORKSPACE_TEST_WHOLE_BODY, 'Requires run_whole_character_check.py fixture.');
  const body = `factory-${'d'.repeat(24)}-body`;
  const current = await request.get('/api/avatars/me').then(r => r.json());
  const result = await request.put('/api/avatars/me', {
    headers: { 'If-Match': current.revision, 'Idempotency-Key': 'whole-character-browser' },
    data: { body, equipment: {} },
  });
  expect(result.ok()).toBeTruthy();
  const errors: string[] = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.goto('/avatar.html?view=wardrobe');
  await expect(page.locator('.avatar-preview')).toHaveAttribute('data-skeleton-id', /.+/);
  await expect(page.locator('.avatar-viewport')).toHaveAttribute('data-renderer', /webgpu|webgl-fallback/);
  await page.getByRole('button', { name: 'Walk', exact: true }).click();
  await expect(page.locator('.avatar-preview')).toHaveAttribute('data-animation', 'walk');
  await page.reload();
  await expect(page.locator('.avatar-preview')).toHaveAttribute('data-skeleton-id', /.+/);
  const restored = await request.get('/api/avatars/me').then(r => r.json());
  expect(restored.state).toMatchObject({ body, equipment: {} });
  expect(errors).toEqual([]);
  await page.screenshot({ path: 'test-results/whole-character.png', fullPage: true });
});
