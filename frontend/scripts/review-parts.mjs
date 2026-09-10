import { chromium } from '@playwright/test';
import fs from 'node:fs/promises';
const browser = await chromium.launch({ channel: 'chromium' });
const page = await browser.newPage({ viewport: { width: 1500, height: 1000 } });
const errors = []; page.on('pageerror', e => errors.push(e.message));
const frame = () => page.evaluate(() => new Promise(resolve => { let n = 0; const f = () => ++n > 12 ? resolve() : requestAnimationFrame(f); f(); }));
try {
  await page.goto('http://127.0.0.1:5273/#A');
  await page.locator('#model-loading').waitFor({ state: 'hidden', timeout: 60000 });
  await page.locator('#expand-world').click();
  await page.locator('#edit-parts').click(); await frame();
  const detail = await (await page.request.get('http://127.0.0.1:5273/api/characters/A')).json();
  await fs.mkdir('test-results/parts-review', { recursive: true });
  for (const role of ['all', 'hat', 'hair', 'head', 'body', 'top', 'skirt', 'shoes', 'without_hat']) {
    for (const part of detail.parts) {
      const visible = role === 'all' || role === part.role || (role === 'without_hat' && part.role !== 'hat');
      await page.locator(`[data-visible="${part.name}"]`).evaluate((input, checked) => { input.checked = checked; input.dispatchEvent(new Event('change')); }, visible);
    }
    await frame(); await page.locator('#viewer').screenshot({ path: `test-results/parts-review/${role}.png` });
  }
  console.log(JSON.stringify({ model: detail.model_sha256, parts: detail.parts, errors }));
  if (errors.length) throw new Error(errors.join('\n'));
} finally { await browser.close(); }
