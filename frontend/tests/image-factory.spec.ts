import { test, expect } from '@playwright/test';

// Real isolated API and files, with provider keys deliberately empty.
const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAAFklEQVR4nGNkYPj/nwEPYMInOXwUAAAQXQIOZWZ6QQAAAABJRU5ErkJggg==','base64');

test('image upload, layer save, lost response recovery, provider gate and request errors',async({page,request})=>{
  const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/avatar.html');
  await page.getByLabel('캐릭터 이미지 가져오기').setInputFiles({name:'Image Pipeline Fixture.png',mimeType:'image/png',buffer:png});
  await expect(page.getByRole('heading',{name:'Image Pipeline Fixture 파츠 설계'})).toBeVisible();
  await page.getByLabel('선택 파츠 PNG 넣기').setInputFiles({name:'top.png',mimeType:'image/png',buffer:png});
  await expect(page.locator('canvas[aria-label="이미지 파츠 겹침 미리보기"]')).toHaveAttribute('data-layers',/^[1-8]$/);
  await page.getByLabel('파츠 X',{exact:true}).fill('120');
  await page.getByRole('button',{name:'설계 저장 *',exact:true}).click();
  await expect(page.getByRole('status').filter({hasText:'이미지 파츠 설계를 저장했습니다.'})).toBeVisible();
  await expect(page.getByRole('button',{name:'한 캐릭터 파츠 전체 분리',exact:true})).toBeDisabled();
  await page.reload();await expect(page.getByLabel('파츠 X',{exact:true})).toHaveValue('120');
  await page.getByLabel('파츠 X',{exact:true}).fill('145');
  let lost=true;
  await page.route('**/api/avatar-blueprints/*',async route=>{
    if(route.request().method()==='PUT'&&lost){lost=false;await route.fetch();await route.abort();}else await route.continue();
  });
  await page.getByRole('button',{name:'설계 저장 *',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('백엔드에 연결할 수 없습니다');
  await page.reload();await expect(page.getByRole('status').filter({hasText:'같은 요청을 복구'})).toBeVisible();
  await page.getByRole('button',{name:'설계 저장 *',exact:true}).click();
  await expect(page.getByRole('status').filter({hasText:'저장했습니다'})).toBeVisible();
  await page.reload();await expect(page.getByLabel('파츠 X',{exact:true})).toHaveValue('145');
  const id=new URL(page.url()).searchParams.get('character')!;
  const blueprint=await request.get(`/api/avatar-blueprints/${id}`).then(r=>r.json());
  const response=await request.post('/api/avatar-factory/image-jobs',{headers:{'Idempotency-Key':'fixture-no-provider'},data:{character_id:id,source_sha256:blueprint.source_sha256,blueprint_revision:blueprint.revision,image_mode:'generate',production_mode:'character_parts',slots:['body','hairBack','hairFront','hat','top','bottom','shoes'],body_purpose:'wardrobe_base',rig_with_meshy:true,motion_actions:{}}});
  expect(response.status()).toBe(422);expect((await response.json()).error.code).toBe('provider_unavailable');
  await page.route(`**/api/avatar-blueprints/${id}`,route=>route.fulfill({status:404,contentType:'application/json',body:JSON.stringify({detail:'Not Found'})}));
  await page.reload();await expect(page.getByRole('alert')).toContainText('프론트와 백엔드 버전');
  await page.unroute(`**/api/avatar-blueprints/${id}`);await page.getByRole('button',{name:'다시 불러오기'}).click();
  await expect(page.getByLabel('파츠 X',{exact:true})).toHaveValue('145');
  expect(errors).toEqual([]);
  await page.screenshot({path:'test-results/image-factory.png',fullPage:true});
});

test('production response loss reuses the same paid request and restores per-part progress',async({page})=>{
  await page.goto('/avatar.html');
  await page.getByLabel('캐릭터 이미지 가져오기').setInputFiles({name:'Production Receipt Fixture.png',mimeType:'image/png',buffer:png});
  await expect(page.getByRole('heading',{name:'Production Receipt Fixture 파츠 설계'})).toBeVisible();
  // Only provider execution is simulated here. Character/image/blueprint APIs remain real.
  const id=new URL(page.url()).searchParams.get('character')!;
  const keys:string[]=[];let saved:Record<string,unknown>|null=null;
  const partSlots=['hairBack','hairFront','hat','top','bottom','shoes'];
  const prior={id:'e'.repeat(24),character_id:id,character_name:'Production Receipt Fixture',source_sha256:'',input_kind:'image',status:'review_required',created_at:'2026-01-01T00:00:00Z',progress:{stage:'review',message:'검수 후보'},artifacts:[],parts:partSlots.map(slot=>({slot,image_status:'succeeded',model_status:'ready'})),next_actions:[]};
  await page.route('**/api/avatar-factory/capabilities',route=>route.fulfill({json:{ready:true,image_configured:true,meshy_configured:true,blender_available:true,slots:['body',...partSlots],next_actions:[{id:'produce_images',enabled:true},{id:'produce_prepared',enabled:true}]}}));
  await page.route('**/api/avatar-factory/jobs',route=>route.fulfill({json:{jobs:saved?[saved,prior]:[prior]}}));
  await page.route('**/api/avatar-factory/image-jobs',async route=>{
    keys.push(route.request().headers()['idempotency-key']!);
    const input=route.request().postDataJSON();
    expect(input.character_id).toBe(id);expect(input.production_mode).toBe('character_parts');expect(input.slots).toEqual(['body',...partSlots]);
    expect(input.body_purpose).toBe('wardrobe_base');expect(input.rig_with_meshy).toBe(true);expect(input.reuse_job_id).toBe(prior.id);
    if(!saved){saved={id:'f'.repeat(24),character_id:id,character_name:'Production Receipt Fixture',source_sha256:input.source_sha256,input_kind:'image',production_mode:'character_parts',status:'pipeline_running',created_at:new Date().toISOString(),progress:{stage:'images',message:'파츠 이미지 생성 중'},artifacts:[],parts:input.slots.map((slot:string)=>({slot,image_status:'pending',model_status:'pending'})),next_actions:[]};await route.abort();}
    else await route.fulfill({status:202,json:saved});
  });
  prior.source_sha256=(await page.evaluate(()=>fetch('/api/avatar-blueprints/'+new URL(location.href).searchParams.get('character')).then(r=>r.json()).then(v=>v.source_sha256))) as string;
  await page.reload();
  await expect(page.getByRole('radio',{name:'7파트 모두 새로 생성 · 기본'})).toBeChecked();
  await page.getByRole('radio',{name:'검증 가능한 기존 분리 파츠 재사용'}).check();
  await expect(page.getByText('신규 유료 예상 이미지 1회 + Meshy 1회')).toBeVisible();
  await expect(page.getByRole('button',{name:'한 캐릭터 파츠 전체 분리',exact:true})).toBeEnabled();
  await page.getByRole('button',{name:'한 캐릭터 파츠 전체 분리',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('백엔드에 연결할 수 없습니다');
  await page.reload();await expect(page.getByRole('button',{name:'같은 생산 요청 복구'})).toBeEnabled();
  await page.getByRole('button',{name:'같은 생산 요청 복구'}).click();
  expect(keys).toHaveLength(2);expect(keys[0]).toBe(keys[1]);
  await expect(page.locator('.image-production-parts>div')).toHaveCount(7);
  saved={...saved!,status:'pipeline_paused',error:'상의: Meshy 응답 유실. 기존 작업 ID 확인이 필요합니다.',artifacts:[{name:'generated-hairBack.glb',url:`/api/avatar-factory/jobs/${'f'.repeat(24)}/artifacts/generated-hairBack.glb`}],parts:[{slot:'hairBack',image_status:'succeeded',model_status:'ready',image_asset:'a'.repeat(64)},{slot:'top',image_status:'succeeded',model_status:'submission_uncertain'}],next_actions:[{id:'resume',enabled:false,reason:'기존 작업 ID 확인 필요'}]};
  await page.reload();await expect(page.getByRole('alert')).toContainText('Meshy 응답 유실');
  await expect(page.getByRole('link',{name:'PNG 받기'})).toHaveAttribute('href',`/api/avatar-blueprints/assets/${'a'.repeat(64)}`);
  await expect(page.getByRole('link',{name:'GLB 받기'})).toHaveAttribute('href',`/api/avatar-factory/jobs/${'f'.repeat(24)}/artifacts/generated-hairBack.glb`);
  await expect(page.getByLabel('상의 Meshy 작업 ID')).toBeVisible();
  await expect(page.getByRole('button',{name:'기존 작업 이어가기'})).toBeDisabled();
  expect(keys).toHaveLength(2);
});
