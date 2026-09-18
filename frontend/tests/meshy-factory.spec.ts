import {test, expect} from '@playwright/test';

test('Meshy motion component renders originals and restores defaults through response loss and reconnect', async ({page,request}) => {
  test.skip(process.env.WORKSPACE_TEST_MESHY !== '1', 'Requires isolated Meshy fixture.');
  const jobId = 'c'.repeat(24);
  const errors: string[] = [], paid: string[] = [];
  page.on('pageerror',e => errors.push(e.message));
  page.on('request',r => {if(r.method()==='POST' && r.url().includes('/meshy/')) paid.push(r.url());});
  // The product now opens the assembled character at every old screen URL.
  // Mount the retained motion-settings component separately for its API contract.
  await page.route('**/meshy-motion-test', route => route.fulfill({ contentType: 'text/html', body: `
    <html><body><div id="root"></div><script type="module">
      import RefreshRuntime from '/@react-refresh';
      RefreshRuntime.injectIntoGlobalHook(window);
      window.$RefreshReg$ = () => {}; window.$RefreshSig$ = () => type => type;
      window.__vite_plugin_react_preamble_installed__ = true;
      await import('/tests/fixtures/meshy-motion.tsx');
    </script></body></html>` }));
  await page.goto('/meshy-motion-test');
  await expect(page.locator('[data-meshy-ready]')).toHaveAttribute('data-meshy-ready', /^[a-f0-9]{24}$/);
  await expect(page.locator('.meshy-scene')).toHaveAttribute('data-renderer', /webgpu|webgl-fallback/);
  await expect(page.locator('.factory-result')).toHaveCount(0);
  await page.locator('.meshy-clips').getByRole('button',{name:'walk',exact:true}).click();
  await expect(page.locator('.meshy-clips').getByRole('button',{name:'walk',exact:true})).toHaveAttribute('aria-pressed','true');
  await page.getByLabel('Meshy 동작 검색').fill('Walk');
  await page.getByLabel('Meshy 동작 목록').selectOption('77');
  let lost = true;
  await page.route('**/api/avatar-factory/motion-defaults', async route => {
    if (route.request().method()==='PUT' && lost) {lost=false; await route.fetch(); await route.abort();}
    else await route.continue();
  });
  await page.getByRole('button',{name:'이 동작을 걷기 기본값으로 저장',exact:true}).click();
  await expect(page.getByRole('status').filter({hasText:'백엔드에 연결할 수 없습니다'})).toBeVisible();
  await page.reload();
  await expect(page.getByLabel('Meshy 동작 목록')).toHaveValue('77');
  await page.getByLabel('기본 동작 슬롯').selectOption('run');
  await page.getByLabel('Meshy 동작 목록').selectOption('14');
  await page.getByRole('button',{name:'이 동작을 달리기 기본값으로 저장',exact:true}).click();
  await expect(page.getByRole('status').filter({hasText:'기본 동작을 저장했습니다'})).toBeVisible();
  const saved = await request.get('/api/avatar-factory/motion-defaults').then(r=>r.json());
  expect(saved.selections).toEqual({walk:77,run:14});
  await page.route(`**/api/avatar-factory/jobs/${jobId}/meshy`,route=>route.abort());
  await page.evaluate(()=>window.dispatchEvent(new Event('online')));
  await expect(page.getByRole('alert')).toContainText('백엔드에 연결할 수 없습니다');
  await page.unroute(`**/api/avatar-factory/jobs/${jobId}/meshy`);
  await page.evaluate(()=>window.dispatchEvent(new Event('online')));
  await expect(page.getByRole('alert')).toHaveCount(0);
  expect(paid).toEqual([]); expect(errors).toEqual([]);
  await page.screenshot({path:'test-results/meshy-factory.png',fullPage:true});
});
