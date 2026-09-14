import { chromium } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

// Read-only live verification. Never saves outfits, submits tasks, or edits source assets.
const base = new URL(process.argv[2] || 'http://127.0.0.1:5273');
if (!['127.0.0.1', 'localhost', '[::1]'].includes(base.hostname)) throw new Error('Local studio URL required');
const output = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../test-results/studio-live');
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ channel: 'chrome', headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  const errors = [], mutations = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', request => { if (!['GET', 'HEAD', 'OPTIONS'].includes(request.method())) mutations.push(request.method()); });
  await page.goto(new URL('/avatar.html?view=wardrobe', base).href);
  await page.getByRole('button', { name: '장착 저장', exact: true }).waitFor({ state: 'visible' });
  await page.locator('.avatar-preview[data-skeleton-id]').waitFor();
  await page.screenshot({ path: path.join(output, 'studio.png'), fullPage: true });
  const backend = await page.locator('.avatar-viewport').getAttribute('data-renderer');
  await page.getByRole('button', { name: '구현 현황', exact: true }).click();
  await page.screenshot({ path: path.join(output, 'implementation.png'), fullPage: true });
  await page.getByRole('button', { name: '구현 현황 닫기' }).click();
  const records = await page.evaluate(async () => (await (await fetch('/api/characters')).json()).characters);
  const source = records.find(character => character.model_id);
  let sourceRenderer;
  if (source) {
    await page.getByRole('button', { name: new RegExp(source.name) }).click();
    await page.locator('.source-model-viewer[data-model-sha256]').waitFor();
    await page.locator('.source-model-viewer[data-renderer="webgpu"], .source-model-viewer[data-renderer="webgl-fallback"]').waitFor();
    await page.locator('.scene-loading').waitFor({ state: 'detached', timeout: 60000 });
    sourceRenderer = await page.locator('.source-model-viewer').getAttribute('data-renderer');
    await page.screenshot({ path: path.join(output, 'character.png'), fullPage: true });
  }
  await page.getByRole('button', { name: '모듈형 아바타 선택' }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
  await page.screenshot({ path: path.join(output, 'mobile.png'), fullPage: true });
  const result = { url: base.href, backend, sourceRenderer, characters: records.length, selectedCharacter: source?.id, overflow, errors, mutations };
  await writeFile(path.join(output, 'result.json'), JSON.stringify(result, null, 2));
  console.log(JSON.stringify(result));
  if (errors.length || mutations.length || overflow) process.exitCode = 1;
} finally { await browser.close(); }
