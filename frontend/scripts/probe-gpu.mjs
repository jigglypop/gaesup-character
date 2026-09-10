import { chromium } from '@playwright/test';

for (const channel of ['chromium', 'msedge']) {
  const browser = await chromium.launch({ channel, headless: true });
  try {
    const page = await browser.newPage();
    await page.goto('http://127.0.0.1:5273/');
    console.log(JSON.stringify({ channel, gpu: await page.evaluate(async () => {
      const adapter = await navigator.gpu?.requestAdapter();
      return { available: !!adapter, info: adapter?.info ? { vendor: adapter.info.vendor, architecture: adapter.info.architecture, description: adapter.info.description } : null };
    }) }));
  } finally { await browser.close(); }
}
