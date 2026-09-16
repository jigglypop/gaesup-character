import { test, expect } from '@playwright/test';

const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAAFklEQVR4nGNkYPj/nwEPYMInOXwUAAAQXQIOZWZ6QQAAAABJRU5ErkJggg==','base64');

test('equipment design saves through live API and delayed saves preserve new edits',async({page,request})=>{
  await page.goto('/avatar.html');
  await page.getByLabel('캐릭터 이미지 가져오기').setInputFiles({name:'Maple Design.png',mimeType:'image/png',buffer:png});
  await expect(page.getByRole('heading',{name:'Maple Design 파츠 설계'})).toBeVisible();
  const id=new URL(page.url()).searchParams.get('character')!;
  await page.locator('.image-layer-list').getByRole('button',{name:/^무기/}).click();
  await page.getByLabel('파츠 제작 요청').fill('파란 수정 지팡이');
  await page.locator('.image-production-slots').getByLabel('무기',{exact:true}).check();
  await page.locator('.image-production-slots').getByLabel('방패',{exact:true}).check();
  await expect(page.locator('.image-production-start')).toContainText('이미지 최대 2회');
  await expect(page.locator('.image-production-slots').getByLabel('머리 포함 전신',{exact:true})).not.toBeChecked();
  await expect(page.locator('.image-production-config')).toContainText('gpt-image-2.5-sunburst');
  await page.getByRole('button',{name:'설계 저장 *',exact:true}).click();
  await expect(page.getByRole('status').filter({hasText:'저장했습니다'})).toBeVisible();
  await page.reload();
  await page.locator('.image-layer-list').getByRole('button',{name:/^무기/}).click();
  await expect(page.getByLabel('파츠 제작 요청')).toHaveValue('파란 수정 지팡이');
  let release!:()=>void;
  let received!:()=>void;
  const started=new Promise<void>(resolve=>{received=resolve;});
  const pending=new Promise<void>(resolve=>{release=resolve;});
  await page.route(`**/api/avatar-blueprints/${id}`,async route=>{
    if(route.request().method()!=='PUT')return route.continue();
    const response=await route.fetch();received();await pending;await route.fulfill({response});
  });
  await page.getByLabel('파츠 제작 요청').fill('초록 수정 지팡이');
  await page.getByRole('button',{name:'설계 저장 *',exact:true}).click();await started;
  await page.getByLabel('파츠 제작 요청').fill('보라 수정 지팡이');release();
  await expect(page.getByRole('button',{name:'설계 저장 *',exact:true})).toBeEnabled();
  await expect(page.getByLabel('파츠 제작 요청')).toHaveValue('보라 수정 지팡이');
  await page.unroute(`**/api/avatar-blueprints/${id}`);
  await page.getByRole('button',{name:'설계 저장 *',exact:true}).click();
  await expect(page.getByRole('status').filter({hasText:'저장했습니다'})).toBeVisible();
  const blueprint=await request.get(`/api/avatar-blueprints/${id}`).then(r=>r.json());
  expect(blueprint.layers).toHaveLength(13);
  expect(blueprint.layers.find((l:{slot:string})=>l.slot==='weapon').description).toBe('보라 수정 지팡이');
  await page.screenshot({path:'test-results/maple-factory-design.png',fullPage:true});
});

test('compiled Maple weapon and shield animate and survive API save and reload',async({page,request})=>{
  test.skip(!process.env.WORKSPACE_TEST_FACTORY_ROOT,'Run run_maple_equipment_check.py and pass its root to test the real compiled files.');
  const prefix=`factory-${'e'.repeat(24)}`;
  const current=await request.get('/api/avatars/me').then(r=>r.json());
  const state={body:`${prefix}-body`,equipment:{hand:`${prefix}-hand`,offhand:`${prefix}-offhand`,back:`${prefix}-back`}};
  const saved=await request.put('/api/avatars/me',{headers:{'If-Match':current.revision,'Idempotency-Key':`maple-fixture-${Date.now()}`},data:state});
  expect(saved.ok()).toBeTruthy();
  await page.goto('/avatar.html?view=wardrobe');
  const preview=page.locator('.avatar-preview');
  await expect(preview).toHaveAttribute('data-skeleton-id',/.+/);
  await expect(page.locator('[data-equipped-slot="hand"]')).toHaveAttribute('data-asset-id',`${prefix}-hand`);
  await expect(page.locator('[data-equipped-slot="offhand"]')).toHaveAttribute('data-asset-id',`${prefix}-offhand`);
  await page.getByRole('button',{name:'Walk',exact:true}).click();
  const result=await page.evaluate(async state=>{
    const path='/src/avatar/runtime/AvatarRuntime.ts';const {AvatarRuntime}=await import(path);
    const {assets}=await fetch('/api/avatars/catalog').then(r=>r.json());
    const avatar=new AvatarRuntime({getAsset:(id:string)=>assets.find((a:{id:string})=>a.id===id)});
    try{
      await avatar.restore({body:state.body,equipment:{}});
      const existing=new Set();avatar.scene.traverse((o:any)=>existing.add(o));
      await avatar.equip('hand',state.equipment.hand);avatar.scene.updateMatrixWorld(true);
      const meshes:any[]=[];avatar.scene.traverse((o:any)=>{if(o.isSkinnedMesh&&!existing.has(o))meshes.push(o);});
      const weapon=meshes[0];if(!weapon)throw new Error('Compiled weapon mesh missing');
      const vertex=()=>{const position=weapon.geometry.attributes.position;const v=weapon.position.clone().fromBufferAttribute(position,0);weapon.applyBoneTransform(0,v);return v;};
      const rest=vertex();avatar.playAnimation('walk');avatar.update(.25);avatar.scene.updateMatrixWorld(true);
      const moved=vertex().distanceTo(rest);
      const time=avatar.getDiagnostics().mixerTime;
      avatar.unequip('offhand');await avatar.equip('offhand',state.equipment.offhand);
      return {moved,sameTime:avatar.getDiagnostics().mixerTime===time,bones:avatar.getDiagnostics().boneCount};
    }finally{avatar.dispose();}
  },state);
  expect(result.moved).toBeGreaterThan(.001);expect(result.sameTime).toBe(true);expect(result.bones).toBe(23);
  await page.getByRole('button',{name:'장착 저장',exact:true}).click();
  await expect(page.getByRole('status')).toContainText('저장했습니다');
  await page.reload();await expect(page.locator('[data-equipped-slot="offhand"]')).toHaveCount(1);
  await page.screenshot({path:'test-results/maple-equipment-runtime.png',fullPage:true});
});
