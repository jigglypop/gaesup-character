import { test, expect } from '@playwright/test';

test('provider centimetre armatures keep their authored rest shape after animation and reset', async ({ page }) => {
  await page.goto('/avatar.html?stage=standard');
  const result = await page.evaluate(async () => {
    const threePath = '/node_modules/three/build/three.module.js';
    const posePath = '/src/model-pose.ts';
    const T = await import(threePath);
    const { captureRestPose } = await import(posePath);
    const scene = new T.Group(), armature = new T.Group(); armature.scale.setScalar(.01); scene.add(armature);
    const bone = new T.Bone(); bone.position.y = 100; armature.add(bone);
    const geometry = new T.BoxGeometry(20, 100, 20).translate(0, 150, 0);
    const count = geometry.attributes.position.count;
    geometry.setAttribute('skinIndex', new T.Uint16BufferAttribute(new Uint16Array(count*4), 4));
    const weights = new Float32Array(count*4); for (let i = 0; i < count; i++) weights[i*4] = 1;
    geometry.setAttribute('skinWeight', new T.Float32BufferAttribute(weights, 4));
    const mesh = new T.SkinnedMesh(geometry, new T.MeshBasicMaterial()); armature.add(mesh);
    scene.updateMatrixWorld(true);
    const skeleton = new T.Skeleton([bone]); mesh.bind(skeleton);
    const inverse = skeleton.boneInverses[0].toArray();
    const sample = () => {
      scene.updateMatrixWorld(true); skeleton.update();
      return Array.from({ length: count }, (_, i) => mesh.applyBoneTransform(i,
        new T.Vector3().fromBufferAttribute(geometry.attributes.position, i)).applyMatrix4(mesh.matrixWorld).toArray()).flat();
    };
    const restore = captureRestPose(scene), before = sample();
    bone.position.x = 35; bone.rotation.z = .4;
    const animated = sample();
    restore(); const after = sample();
    skeleton.pose(); const reconstructed = sample();
    restore(); const repeated = sample();
    const delta = (a: number[], b: number[]) => Math.max(...a.map((v, i) => Math.abs(v-b[i])));
    const value = { restoredError: delta(before, after), repeatedError: delta(before, repeated),
      restBoundsHeight: mesh.boundingBox?.getSize(new T.Vector3()).y,
      animationDelta: delta(before, animated), invalidBindResetDelta: delta(before, reconstructed), inverseUnchanged: JSON.stringify(inverse) === JSON.stringify(skeleton.boneInverses[0].toArray()) };
    geometry.dispose(); mesh.material.dispose(); skeleton.dispose(); return value;
  });
  expect(result.animationDelta).toBeGreaterThan(.1);
  expect(result.invalidBindResetDelta).toBeGreaterThan(.1);
  expect(result.restoredError).toBeLessThan(1e-7);
  expect(result.repeatedError).toBeLessThan(1e-7);
  expect(result.inverseUnchanged).toBe(true);
  expect(result.restBoundsHeight).toBeCloseTo(100, 6);
});
