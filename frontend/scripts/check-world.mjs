import { chromium, expect } from '@playwright/test';

const browser = await chromium.launch({ channel: 'chromium', headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [];
page.on('pageerror', error => errors.push(error.message));
try {
  await page.goto('http://127.0.0.1:5273/');
  const world = page.locator('#viewer');
  await expect(world).toHaveAttribute('data-world', 'gaesup-world', { timeout: 30000 });
  await expect(world).toHaveAttribute('data-renderer', 'webgpu');
  const detail = await (await page.request.get('http://127.0.0.1:5273/api/characters/A')).json();
  await expect(world).toHaveAttribute('data-character-meshes', String(detail.inspection.nodes.length));
  await page.locator('#expand-world').click();
  const position = async () => JSON.parse(await world.getAttribute('data-character-position'));
  await expect.poll(async () => Math.abs((await position()).y)).toBeLessThan(.03);
  await page.locator('canvas').click();
  const before = await position();
  await page.keyboard.down('KeyW');
  await expect.poll(async () => { const p = await position(); return Math.hypot(p.x - before.x, p.z - before.z); }).toBeGreaterThan(.5);
  await page.keyboard.up('KeyW');
  const after = await position();
  await expect.poll(async () => (await position()).y).toBeGreaterThan(-.05);
  await page.locator('#animation').selectOption('0');
  await page.locator('.preview-panel').screenshot({ path: 'test-results/gaesup-world-live.png' });
  console.log(JSON.stringify({ renderer: 'webgpu', world: 'gaesup-world', before, after, model: await world.getAttribute('data-model-sha256'), animation: await page.locator('#animation option:checked').textContent(), errors }));
  expect(errors).toEqual([]);
} finally { await browser.close(); }
