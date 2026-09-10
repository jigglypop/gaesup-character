import { chromium } from '@playwright/test';
import fs from 'node:fs/promises';

const browser = await chromium.launch({ channel: 'chromium' });
const page = await browser.newPage({ viewport: { width: 1500, height: 1000 } });
const errors = []; page.on('pageerror', error => errors.push(error.message));
try {
  await page.goto('http://127.0.0.1:5273/#A');
  await page.locator('#model-loading').waitFor({ state: 'hidden', timeout: 60000 });
  await page.locator('#expand-world').click();
  await page.locator('#edit-parts').click();
  await page.locator('#paint-tools').waitFor({ state: 'visible' });
  await page.evaluate(() => new Promise(resolve => { let n = 0; const frame = () => ++n > 45 ? resolve() : requestAnimationFrame(frame); frame(); }));
  const canvas = await page.locator('#viewer canvas').boundingBox();
  await fs.mkdir('test-results', { recursive: true });
  await page.screenshot({ path: 'test-results/parts-editor-before.png' });
  await page.mouse.click(canvas.x + canvas.width * .5, canvas.y + canvas.height * .45);
  await page.locator('#split-painted:not([disabled])').waitFor({ timeout: 10000 });
  await page.screenshot({ path: 'test-results/parts-editor-painted.png' });
  const count = await page.locator('#paint-count').innerText();
  await page.locator('#paint-undo').click();
  if (!await page.locator('#split-painted').isDisabled()) throw new Error('Undo did not clear the selected stroke');
  await page.locator('#edit-parts').click();
  if (errors.length) throw new Error(errors.join('\n'));
  console.log(JSON.stringify({ selection: count, undo: 'passed', world_return: 'passed', errors }));
} finally { await browser.close(); }
