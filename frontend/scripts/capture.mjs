import { chromium } from '@playwright/test';
import { mkdir } from 'node:fs/promises';

await mkdir('test-results', { recursive: true });
const browser = await chromium.launch({ channel: 'chromium', headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
const errors = [];
page.on('pageerror', error => errors.push(error.message));
await page.goto('http://127.0.0.1:5273/', { waitUntil: 'networkidle' });
await page.locator('.character-card').first().waitFor();
await page.locator('#model-loading').waitFor({ state: 'hidden', timeout: 60000 });
await page.evaluate(() => new Promise(resolve => {
  let frames = 0;
  const tick = () => ++frames >= 90 ? resolve() : requestAnimationFrame(tick);
  requestAnimationFrame(tick);
}));
if (process.argv.includes('--inspect')) {
  await page.locator('[data-action="inspect_model"]').click();
  await page.locator('.operation b').filter({ hasText: '작업 완료' }).waitFor();
  await page.locator('#model-loading').waitFor({ state: 'hidden', timeout: 60000 });
}
await page.screenshot({ path: 'test-results/workspace-live.png', fullPage: true });
await page.locator('.preview-panel').screenshot({ path: 'test-results/gaesup-world-live.png' });
console.log(JSON.stringify({ cards: await page.locator('.character-card').count(),
  canvas: await page.locator('canvas').count(), errors,
  renderer: await page.locator('#viewer').getAttribute('data-renderer'),
  rendererLabel: await page.locator('.renderer-badge').textContent(),
  world: await page.locator('#viewer').getAttribute('data-world'),
  characterPosition: await page.locator('#viewer').getAttribute('data-character-position'),
  characterMeshes: await page.locator('#viewer').getAttribute('data-character-meshes'),
  notice: await page.locator('#notice').textContent() }));
await browser.close();
