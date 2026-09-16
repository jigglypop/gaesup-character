import { chromium, expect } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

const [jobId, address = 'http://127.0.0.1:5273'] = process.argv.slice(2);
if (!/^[a-f0-9]{24}$/.test(jobId || '')) throw new Error('Pass an existing factory job ID');
const base = new URL(address);
if (!['127.0.0.1', 'localhost', '[::1]'].includes(base.hostname)) throw new Error('Local API required');
const output = path.resolve('../data/verification', 'meshy-' + jobId + '-' + Date.now());
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ channel: 'chrome', headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1500, height: 1100 } });
  const errors = [], mutations = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/*', async route => {
    if (!['GET', 'HEAD', 'OPTIONS'].includes(route.request().method())) {
      mutations.push(route.request().method() + ' ' + new URL(route.request().url()).pathname);
      await route.abort(); return;
    }
    await route.continue();
  });
  await page.goto(new URL('/avatar.html?stage=glb&character=A&job=' + jobId + '&tab=result', base).href);
  await expect(page.locator('[data-meshy-ready]')).toHaveAttribute('data-meshy-ready', /^[a-f0-9]{24}$/, {timeout: 90000});
  await expect(page.locator('.factory-result')).toHaveCount(0);
  const backend = await page.locator('.meshy-scene').getAttribute('data-renderer');
  await expect(page.locator('.meshy-scene')).toHaveAttribute('data-renderer', /webgpu|webgl-fallback/);
  const state = await page.evaluate(id => fetch('/api/avatar-factory/jobs/'+id+'/meshy').then(r => r.json()), jobId);
  const model = state.artifacts.find(a => a.name === 'model.glb');
  const runtime = await page.evaluate(async url => {
    const {GLTFLoader} = await import('/node_modules/three/examples/jsm/loaders/GLTFLoader.js');
    const THREE = await import('/node_modules/three/build/three.module.js');
    const gltf = await new GLTFLoader().loadAsync(url);
    const meshes = []; gltf.scene.traverse(o => {if (o.isSkinnedMesh) meshes.push(o);});
    const boneCount = new Set(meshes.flatMap(m => m.skeleton.bones)).size;
    const mixer = new THREE.AnimationMixer(gltf.scene);
    const snapshot = () => {
      gltf.scene.updateMatrixWorld(true); meshes.forEach(m => m.skeleton.update());
      return meshes.flatMap(m => Array.from({length: Math.min(200, m.geometry.attributes.position.count)}, (_, index) => {
        const i = Math.floor(index*m.geometry.attributes.position.count/Math.min(200,m.geometry.attributes.position.count));
        const v = new THREE.Vector3().fromBufferAttribute(m.geometry.attributes.position, i);
        m.applyBoneTransform(i, v); return v.applyMatrix4(m.matrixWorld);
      }));
    };
    const motion = {};
    for (const name of ['walk', 'run']) {
      mixer.stopAllAction(); mixer.clipAction(gltf.animations.find(c => c.name === name)).reset().play();
      mixer.update(.01); const before = snapshot(); let delta = 0;
      for(let frame=0; frame<12; frame++) {mixer.update(.05); snapshot().forEach((v,i) => {delta = Math.max(delta,v.distanceTo(before[i]));});}
      motion[name] = delta;
    }
    mixer.stopAllAction(); mixer.uncacheRoot(gltf.scene);
    return {boneCount, clips:gltf.animations.map(c=>c.name), motion};
  }, model.url);
  expect(runtime.boneCount).toBe(state.bone_count);
  expect(runtime.motion.walk).toBeGreaterThan(.001); expect(runtime.motion.run).toBeGreaterThan(.001);
  await page.screenshot({path: path.join(output,'rest.png'), fullPage:true});
  for (const name of ['walk','run']) {
    await page.locator('.meshy-clips').getByRole('button',{name,exact:true}).click();
    await expect(page.locator('.meshy-clips').getByRole('button',{name,exact:true})).toHaveAttribute('aria-pressed','true');
    await page.screenshot({path:path.join(output,name+'.png'), fullPage:true});
  }
  await expect(page.getByLabel('Meshy 동작 목록').locator('option')).not.toHaveCount(1);
  await page.getByLabel('Meshy 동작 검색').fill('Run 2');
  await page.getByLabel('Meshy 동작 목록').selectOption('14');
  await expect(page.getByAltText('Run 2 Meshy 동작 미리보기')).toBeVisible();
  await expect.poll(() => page.getByAltText('Run 2 Meshy 동작 미리보기').evaluate(i => i.naturalWidth)).toBeGreaterThan(0);
  await page.screenshot({path:path.join(output,'picker.png'),fullPage:true});
  await page.reload();
  await expect(page.locator('[data-meshy-ready]')).toHaveAttribute('data-meshy-ready', state.version, {timeout:90000});
  const result = {jobId, url:page.url(), backend, state, runtime, reload:true, errors, mutations, output};
  await writeFile(path.join(output,'result.json'),JSON.stringify(result,null,2));
  expect(errors).toEqual([]); expect(mutations).toEqual([]);
  console.log(JSON.stringify(result));
} finally {await browser.close();}
