import { Group, Matrix4, Skeleton, Vector3, type Bone, type Object3D, type SkinnedMesh, type Texture, type Material, type BufferGeometry } from 'three';
import { GLTFLoader, type GLTF } from 'three/addons/loaders/GLTFLoader.js';

export type Wearable = { id: string; slot: string; url: string; sha256: string };
type Entry = { spec: Wearable; group: Group; source: GLTF; skeletons: Set<Skeleton>; touched: number };
type RestBone = { bone: Bone; matrix: Matrix4; parent: string | null };

function disposeEntry(entry: Entry) {
  entry.group.removeFromParent();
  const textures = new Set<Texture>(), materials = new Set<Material>(), geometries = new Set<BufferGeometry>();
  for (const root of [entry.group, entry.source.scene]) root.traverse(object => {
    const mesh = object as SkinnedMesh;
    if (!mesh.isMesh) return;
    geometries.add(mesh.geometry);
    for (const material of Array.isArray(mesh.material) ? mesh.material : [mesh.material]) {
      materials.add(material);
      for (const value of Object.values(material)) if (value && (value as Texture).isTexture) textures.add(value as Texture);
    }
    if (mesh.isSkinnedMesh) entry.skeletons.add(mesh.skeleton);
  });
  textures.forEach(texture => { (texture.source.data as ImageBitmap)?.close?.(); texture.dispose(); });
  materials.forEach(material => material.dispose()); geometries.forEach(geometry => geometry.dispose());
  entry.skeletons.forEach(skeleton => skeleton.dispose());
}

/** Variant meshes share the loaded body's actual bone objects and mixer.
 * Source bytes, bone order, bind matrices, geometry, UVs and weights stay intact.
 */
export class NativeWardrobe {
  private bones = new Map<string, RestBone>();
  private baseInverse: Matrix4;
  private active = new Map<string, Entry>();
  private loaded = new Map<string, Entry>();
  private loading = new Map<string, Promise<Entry>>();
  private references = new Map<string, number>();
  private generation = 0;
  private disposed = false;

  constructor(private body: Object3D) {
    body.updateMatrixWorld(true); this.baseInverse = body.matrixWorld.clone().invert();
    const rigs = new Set<Skeleton>();
    body.traverse(object => { const mesh = object as SkinnedMesh; if (mesh.isSkinnedMesh) rigs.add(mesh.skeleton); });
    for (const rig of rigs) for (const bone of rig.bones) {
      const prior = this.bones.get(bone.name);
      if (!bone.name || (prior && prior.bone !== bone)) throw new Error('기준 몸의 본 이름이 중복되어 의상을 연결할 수 없습니다.');
      this.bones.set(bone.name, { bone, matrix: this.baseInverse.clone().multiply(bone.matrixWorld), parent: (bone.parent as Bone)?.isBone ? bone.parent!.name : null });
    }
    if (!this.bones.size) throw new Error('기준 몸의 공용 골격이 없습니다.');
  }

  private async load(spec: Wearable): Promise<Entry> {
    const cached = this.loaded.get(spec.id);
    if (cached) {
      if (cached.spec.sha256 !== spec.sha256 || cached.spec.slot !== spec.slot || cached.spec.url !== spec.url) throw new Error('같은 의상의 파일 버전이 변경되었습니다.');
      cached.touched = performance.now(); return cached;
    }
    const pending = this.loading.get(spec.id);
    if (pending) {
      const entry = await pending;
      if (entry.spec.sha256 !== spec.sha256 || entry.spec.slot !== spec.slot || entry.spec.url !== spec.url) throw new Error('동시에 선택한 의상 버전이 다릅니다.');
      return entry;
    }
    const request = (async () => {
      const response = await fetch(spec.url);
      if (!response.ok) throw new Error('의상 모델을 불러올 수 없습니다.');
      const bytes = await response.arrayBuffer();
      const digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))).map(v => v.toString(16).padStart(2, '0')).join('');
      if (digest !== spec.sha256) throw new Error('의상 파일이 검수한 버전과 다릅니다.');
      const source = await new GLTFLoader().parseAsync(bytes, '');
      const entry: Entry = { spec, source, group: new Group(), skeletons: new Set(), touched: performance.now() };
      try {
        if (this.disposed) throw new Error('옷장 화면이 닫혔습니다.');
        source.scene.updateMatrixWorld(true);
        const meshes: SkinnedMesh[] = [];
        source.scene.traverse(object => { if ((object as SkinnedMesh).isSkinnedMesh) meshes.push(object as SkinnedMesh); });
        if (!meshes.length || meshes.some(mesh => mesh.userData.standard_slot !== spec.slot)) throw new Error('공용 골격에 맞춘 해당 슬롯의 의상 파일이 필요합니다.');
        for (const mesh of meshes) {
          const native = mesh.skeleton;
          if (native.bones.length !== this.bones.size) throw new Error('의상의 골격 규격이 기준 몸과 다릅니다.');
          const names = new Set<string>();
          const targets = native.bones.map(bone => {
            const rest = this.bones.get(bone.name);
            const parent = (bone.parent as Bone)?.isBone ? bone.parent!.name : null;
            if (!rest || names.has(bone.name) || rest.parent !== parent ||
                rest.matrix.elements.some((v, i) => Math.abs(v - bone.matrixWorld.elements[i]) > 1e-4)) {
              throw new Error('의상의 본 위치·구조가 고정 몸과 맞지 않습니다. 다시 피팅해야 합니다.');
            }
            names.add(bone.name); return rest.bone;
          });
          const transform = this.baseInverse.clone().multiply(mesh.matrixWorld);
          entry.skeletons.add(native);
          // Keep this mesh's bind matrices and bone index order. Only substitute
          // the verified equal-rest-pose bone objects, never recompute inverse binds.
          mesh.skeleton = new Skeleton(targets, native.boneInverses.map(matrix => matrix.clone()));
          entry.skeletons.add(mesh.skeleton);
          mesh.removeFromParent(); transform.decompose(mesh.position, mesh.quaternion, mesh.scale); mesh.updateMatrix();
          mesh.name = `wardrobe-${spec.id}-${entry.group.children.length}`;
          mesh.userData.wardrobePartId = spec.id; entry.group.add(mesh);
        }
        this.loaded.set(spec.id, entry); return entry;
      } catch (error) { disposeEntry(entry); throw error; }
    })();
    this.loading.set(spec.id, request);
    try { return await request; } finally { this.loading.delete(spec.id); }
  }

  async equip(parts: Wearable[]): Promise<boolean> {
    if (this.disposed) throw new Error('옷장 화면이 닫혔습니다.');
    if (new Set(parts.map(p => p.slot)).size !== parts.length || new Set(parts.map(p => p.id)).size !== parts.length) throw new Error('한 슬롯에는 의상 하나만 선택하세요.');
    const generation = ++this.generation;
    parts.forEach(part => this.references.set(part.id, (this.references.get(part.id) || 0)+1));
    try {
      const results = await Promise.allSettled(parts.map(part => this.load(part)));
      const failure = results.find(result => result.status === 'rejected');
      if (failure?.status === 'rejected') throw failure.reason;
      const entries = results.map(result => (result as PromiseFulfilledResult<Entry>).value);
      if (this.disposed || generation !== this.generation) return false;
      // Commit all slots together after every file passed. Failed loads retain
      // the previous outfit and the existing animation keeps advancing.
      this.active.forEach(entry => entry.group.removeFromParent());
      this.active = new Map(entries.map(entry => [entry.spec.slot, entry]));
      entries.forEach(entry => { entry.touched = performance.now(); this.body.add(entry.group); });
      this.body.updateMatrixWorld(true); return true;
    } finally {
      parts.forEach(part => { const count = (this.references.get(part.id) || 1)-1; if (count) this.references.set(part.id, count); else this.references.delete(part.id); });
      const active = new Set(Array.from(this.active.values(), entry => entry.spec.id));
      const inactive = Array.from(this.loaded.values()).filter(entry => !active.has(entry.spec.id) && !this.references.has(entry.spec.id)).sort((a,b) => b.touched-a.touched);
      for (const entry of inactive.slice(2)) { this.loaded.delete(entry.spec.id); disposeEntry(entry); }
    }
  }

  diagnostics() {
    const sample: number[] = []; let shared = true;
    this.body.updateMatrixWorld(true);
    this.active.forEach(entry => entry.group.traverse(object => {
      const mesh = object as SkinnedMesh; if (!mesh.isSkinnedMesh) return;
      shared &&= mesh.skeleton.bones.every(bone => this.bones.get(bone.name)?.bone === bone);
      mesh.skeleton.update();
      const count = mesh.geometry.attributes.position.count;
      for (let i = 0; i < count; i += Math.max(1, Math.floor(count/8))) {
        const point = new Vector3().fromBufferAttribute(mesh.geometry.attributes.position, i);
        mesh.applyBoneTransform(i, point).applyMatrix4(mesh.matrixWorld); sample.push(point.x, point.y, point.z);
      }
    }));
    return { partIds: Array.from(this.active.values(), entry => entry.spec.id), boneCount: this.bones.size, shared, sample };
  }

  dispose() { this.disposed = true; this.generation++; this.loaded.forEach(disposeEntry); this.loaded.clear(); this.active.clear(); }
}
