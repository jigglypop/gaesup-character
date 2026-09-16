import { chromium, expect } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

const [item, address = 'http://127.0.0.1:5273', referenceCharacter] = process.argv.slice(2);
if (!/^[a-f0-9]{24}$/.test(item || '')) throw new Error('Pass an existing unapproved standard body ID');
const base = new URL(address);
if (!['127.0.0.1', 'localhost', '[::1]'].includes(base.hostname)) throw new Error('Local API required');
const output = path.resolve('../data/verification', `standard-batch-${item}-${Date.now()}`);
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ channel: 'chrome', headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1500, height: 1100 } });
  const errors = [], mutations = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/*', async route => {
    if (!['GET', 'HEAD', 'OPTIONS'].includes(route.request().method())) {
      mutations.push(route.request().method()+' '+new URL(route.request().url()).pathname);
      await route.abort(); return;
    }
    await route.continue();
  });
  const pageUrl = new URL(`/avatar.html?stage=standard&item=${item}`, base);
  if (referenceCharacter) pageUrl.searchParams.set('character', referenceCharacter);
  await page.goto(pageUrl.href);
  await expect(page.locator('[data-standard-preview]')).toHaveAttribute('data-standard-preview', item);
  await expect(page.locator('[data-standard-preview]')).toHaveAttribute('data-standard-ready', item, { timeout: 90000 });
  await expect(page.locator('.standard-scene')).toHaveAttribute('data-renderer', /webgpu|webgl-fallback/);
  const renderer = await page.locator('.standard-scene').getAttribute('data-renderer');
  for (let i = 0; i < 3; i++) {
    const response = page.waitForResponse(r => r.url().endsWith('/api/avatar-standard/items'));
    await page.evaluate(() => window.dispatchEvent(new Event('online')));
    await response;
  }
  await expect(page.locator('[data-standard-preview]')).toHaveCount(1);
  await expect(page.getByRole('region', { name: '의상 일괄 생산' })).toBeVisible();
  let referenceSha256 = null;
  if (referenceCharacter) {
    const panel = page.getByRole('region', { name: '의상 일괄 생산' });
    await expect(panel.getByLabel('배치 참고 원본')).toHaveValue(referenceCharacter);
    await expect(panel.locator('.batch-reference img')).toBeVisible();
    referenceSha256 = await panel.locator('.batch-reference img').evaluate(async image => {
      const response = await fetch(image.src);
      const hash = await crypto.subtle.digest('SHA-256', await response.arrayBuffer());
      return Array.from(new Uint8Array(hash), v => v.toString(16).padStart(2, '0')).join('');
    });
    await panel.screenshot({ path: path.join(output, 'reference-and-batch.png') });
  }
  const state = await page.evaluate(id => fetch(`/api/avatar-standard/items/${id}`).then(r => r.json()), item);
  expect(state.status).toBe('review_required');
  await page.screenshot({ path: path.join(output, 'candidate-and-batch.png'), fullPage: true });
  await page.reload();
  await expect(page.locator('[data-standard-preview]')).toHaveAttribute('data-standard-preview', item);
  await expect(page.locator('[data-standard-preview]')).toHaveAttribute('data-standard-ready', item, { timeout: 90000 });
  await expect(page.locator('.standard-scene')).toHaveAttribute('data-renderer', /webgpu|webgl-fallback/);
  if (referenceCharacter) await expect(page.getByLabel('배치 참고 원본')).toHaveValue(referenceCharacter);
  expect(errors).toEqual([]); expect(mutations).toEqual([]);
  await writeFile(path.join(output, 'report.json'), JSON.stringify({ renderer, errors, mutations, source: item,
    model_sha256: state.model_sha256, review: state.review, visualApproval: false, referenceCharacter, referenceSha256 }, null, 2));
  console.log(JSON.stringify({ output, renderer, errors, mutations }));
} finally { await browser.close(); }
