import * as THREE from 'three';
import type { GLTF } from 'three/addons/loaders/GLTFLoader.js';

export const expressionNames = { neutral: '기본', smile: '웃음', cry: '울음', angry: '화남', surprise: '놀람', blink: '눈 감기' };
export type ExpressionName = keyof typeof expressionNames;
export type FaceLayout = { eye: number; mouth: number; spacing: number; size: number };
export const defaultFaceLayout: FaceLayout = { eye: .64, mouth: .86, spacing: .21, size: 1 };
export type ExpressionMap = { material: number; png: string };
type Surface = { material: THREE.MeshStandardMaterial; index: number; original: THREE.Texture; canvas: HTMLCanvasElement; context: CanvasRenderingContext2D };
type Face = { surface: Surface; xy: number[]; uv: number[] };

/** Paint the existing UV atlas once per expression. No added meshes or per-frame work. */
export class TextureExpressions {
  private surfaces = new Map<THREE.Material, Surface>();
  private faces: Face[] = [];
  private replacements: THREE.Texture[] = [];
  private disposed = false;
  private sequence = 0;
  private box = new THREE.Box3();
  constructor(private gltf: GLTF) {
    const meshes: THREE.SkinnedMesh[] = [];
    gltf.scene.updateMatrixWorld(true);
    gltf.scene.traverse(object => {
      if (!(object instanceof THREE.SkinnedMesh)) return;
      const ids = object.skeleton.bones.map((bone, i) => /(^|:)head$/i.test(bone.name) ? i : -1).filter(i => i >= 0);
      if (!ids.length) return;
      meshes.push(object);
      const geometry = object.geometry, joints = geometry.getAttribute('skinIndex'), weights = geometry.getAttribute('skinWeight');
      for (let i = 0; i < geometry.getAttribute('position').count; i++) {
        let head = 0;
        for (let j = 0; j < 4; j++) if (ids.includes(joints.getComponent(i, j))) head += weights.getComponent(i, j);
        if (head > .6) this.box.expandByPoint(new THREE.Vector3().fromBufferAttribute(geometry.getAttribute('position'), i).applyMatrix4(object.matrixWorld));
      }
    });
    if (this.box.isEmpty()) throw new Error('머리 관절이 연결된 기본 몸이 필요합니다.');
    const size = this.box.getSize(new THREE.Vector3());
    for (const mesh of meshes) {
      const g = mesh.geometry, uv = g.getAttribute('uv'), position = g.getAttribute('position');
      if (!uv) continue;
      const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
      const count = g.index?.count ?? position.count;
      for (let i = 0; i < count; i += 3) {
        const ids = [0, 1, 2].map(j => g.index?.getX(i+j) ?? i+j);
        const points = ids.map(j => new THREE.Vector3().fromBufferAttribute(position, j).applyMatrix4(mesh.matrixWorld));
        const normal = points[1].clone().sub(points[0]).cross(points[2].clone().sub(points[0])).normalize();
        if (normal.z < .18 || points.some(p => p.y < this.box.min.y || p.z < this.box.min.z+size.z*.45)) continue;
        const group = g.groups.find(group => i >= group.start && i < group.start+group.count);
        const material = materials[group?.materialIndex ?? 0];
        if (!(material instanceof THREE.MeshStandardMaterial) || !material.map) continue;
        const index = gltf.parser.associations.get(material)?.materials;
        if (index === undefined) continue;
        let surface = this.surfaces.get(material);
        if (!surface) {
          const canvas = document.createElement('canvas');
          const image = material.map.image as { width: number; height: number };
          const scale = Math.min(1, 1024/Math.max(image.width, image.height));
          canvas.width = Math.max(1, Math.round(image.width*scale)); canvas.height = Math.max(1, Math.round(image.height*scale));
          surface = { material, index, original: material.map, canvas, context: canvas.getContext('2d')! };
          this.surfaces.set(material, surface);
        }
        this.faces.push({ surface,
          xy: points.flatMap(p => [(p.x-this.box.min.x)/size.x*512, (this.box.max.y-p.y)/size.y*512]),
          uv: ids.flatMap(j => [uv.getX(j)*surface!.canvas.width, uv.getY(j)*surface!.canvas.height]),
        });
      }
    }
    if (!this.faces.length) throw new Error('얼굴의 UV 텍스쳐를 찾을 수 없습니다.');
  }
  private restore() {
    this.surfaces.forEach(s => { s.material.map = s.original; s.material.needsUpdate = true; });
    this.replacements.forEach(t => { (t.image as ImageBitmap)?.close?.(); t.dispose(); }); this.replacements = [];
  }
  async apply(name: ExpressionName, layout: FaceLayout): Promise<ExpressionMap[]> {
    const sequence = ++this.sequence;
    this.restore();
    if (name === 'neutral') return [];
    this.surfaces.forEach(s => {
      s.context.clearRect(0, 0, s.canvas.width, s.canvas.height);
      s.context.drawImage(s.original.image, 0, 0, s.canvas.width, s.canvas.height);
    });
    // Sample each triangle's own cheek color to retain the base skin palette.
    const colorSurface = this.faces.find(f => f.xy.some((value, i) => i % 2 && value > 375)) || this.faces[0];
    const c = colorSurface.surface.context.getImageData(Math.max(0, Math.min(colorSurface.surface.canvas.width-1, Math.round(colorSurface.uv[0]))), Math.max(0, Math.min(colorSurface.surface.canvas.height-1, Math.round(colorSurface.uv[1]))), 1, 1).data;
    const art = drawFace(name, layout, `rgb(${c[0]},${c[1]},${c[2]})`);
    for (let i = 0; i < this.faces.length; i++) {
      if (this.disposed || sequence !== this.sequence) return [];
      const { surface, xy: p, uv: q } = this.faces[i];
      const determinant = (p[2]-p[0])*(p[5]-p[1])-(p[4]-p[0])*(p[3]-p[1]);
      if (Math.abs(determinant) < .001) continue;
      const a = ((q[2]-q[0])*(p[5]-p[1])-(q[4]-q[0])*(p[3]-p[1]))/determinant;
      const c = ((p[2]-p[0])*(q[4]-q[0])-(p[4]-p[0])*(q[2]-q[0]))/determinant;
      const b = ((q[3]-q[1])*(p[5]-p[1])-(q[5]-q[1])*(p[3]-p[1]))/determinant;
      const d = ((p[2]-p[0])*(q[5]-q[1])-(p[4]-p[0])*(q[3]-q[1]))/determinant;
      const ctx = surface.context;
      ctx.save(); ctx.beginPath(); ctx.moveTo(q[0], q[1]); ctx.lineTo(q[2], q[3]); ctx.lineTo(q[4], q[5]); ctx.closePath(); ctx.clip();
      ctx.setTransform(a, b, c, d, q[0]-a*p[0]-c*p[1], q[1]-b*p[0]-d*p[1]); ctx.drawImage(art, 0, 0); ctx.restore();
      if (i % 400 === 399) await new Promise(resolve => setTimeout(resolve, 0));
    }
    if (this.disposed || sequence !== this.sequence) return [];
    return [...this.surfaces.values()].map(s => {
      const texture = new THREE.CanvasTexture(s.canvas);
      texture.flipY = false; texture.colorSpace = THREE.SRGBColorSpace;
      texture.wrapS = s.original.wrapS; texture.wrapT = s.original.wrapT;
      texture.channel = s.original.channel; texture.generateMipmaps = true;
      s.material.map = texture; s.material.needsUpdate = true; this.replacements.push(texture);
      return { material: s.index, png: s.canvas.toDataURL('image/png').split(',')[1] };
    });
  }
  dispose() { this.disposed = true; this.sequence++; this.restore(); }
  async saved(maps: { material: number; url: string; sha256: string }[]) {
    const sequence = ++this.sequence;
    const loaded = await Promise.allSettled(maps.map(async map => {
      const response = await fetch(map.url, { signal: AbortSignal.timeout(20000) });
      if (!response.ok) throw new Error('저장된 표정 텍스쳐를 불러올 수 없습니다.');
      const bytes = await response.arrayBuffer();
      const sha = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))).map(n => n.toString(16).padStart(2, '0')).join('');
      if (sha !== map.sha256) throw new Error('저장된 표정 텍스쳐가 변경되었습니다.');
      return { ...map, image: await createImageBitmap(new Blob([bytes], { type: 'image/png' }), { colorSpaceConversion: 'none', premultiplyAlpha: 'none' }) };
    }));
    const failure = loaded.find(r => r.status === 'rejected');
    if (this.disposed || sequence !== this.sequence || failure) {
      loaded.forEach(r => { if (r.status === 'fulfilled') r.value.image.close(); });
      if (failure?.status === 'rejected') throw failure.reason;
      return;
    }
    this.restore();
    for (const result of loaded) if (result.status === 'fulfilled') {
      const surface = [...this.surfaces.values()].find(s => s.index === result.value.material);
      if (!surface) { result.value.image.close(); continue; }
      const texture = surface.original.clone(); texture.image = result.value.image; texture.needsUpdate = true;
      surface.material.map = texture; surface.material.needsUpdate = true; this.replacements.push(texture);
    }
  }
}

function drawFace(name: ExpressionName, layout: FaceLayout, skin: string) {
  const canvas = document.createElement('canvas'); canvas.width = canvas.height = 512;
  const c = canvas.getContext('2d')!, eye = layout.eye*512, mouth = layout.mouth*512, scale = layout.size;
  const patch = (x: number, y: number, rx: number, ry: number) => {
    c.save(); c.translate(x, y); c.scale(rx, ry);
    const gradient = c.createRadialGradient(0, 0, .65, 0, 0, 1);
    gradient.addColorStop(0, skin); gradient.addColorStop(1, skin.replace('rgb(', 'rgba(').replace(')', ',0)'));
    c.fillStyle = gradient; c.fillRect(-1, -1, 2, 2); c.restore();
  };
  const line = (x: number, y: number, bend: number, width: number, color = '#69414b') => {
    c.strokeStyle = color; c.lineWidth = 4*scale; c.lineCap = 'round';
    c.beginPath(); c.moveTo(x-width/2, y); c.quadraticCurveTo(x, y+bend, x+width/2, y); c.stroke();
  };
  patch(256, mouth, 42*scale, 29*scale);
  if (name === 'smile') line(256, mouth-6*scale, 28*scale, 45*scale);
  if (name === 'cry' || name === 'angry') line(256, mouth+6*scale, -18*scale, 33*scale);
  if (name === 'surprise') { c.fillStyle = '#74434f'; c.beginPath(); c.ellipse(256, mouth, 12*scale, 18*scale, 0, 0, Math.PI*2); c.fill(); }
  if (name === 'blink') line(256, mouth, 4*scale, 19*scale);
  for (const sign of [-1, 1]) {
    const x = 256+sign*layout.spacing*512;
    if (name === 'blink') { patch(x, eye, 60*scale, 60*scale); line(x, eye, 14*scale, 72*scale); }
    if (name === 'cry') {
      c.fillStyle = 'rgba(131,206,245,.85)'; c.beginPath(); c.roundRect(x-12*scale, eye+22*scale, 17*scale, 51*scale, 8*scale); c.fill();
      c.strokeStyle = '#d2f3ff'; c.lineWidth = 3*scale; c.beginPath(); c.moveTo(x-7*scale, eye+30*scale); c.lineTo(x-7*scale, eye+60*scale); c.stroke();
    }
    if (name === 'angry') {
      const y = eye-55*scale; patch(x, y, 50*scale, 19*scale);
      c.strokeStyle = '#65424a'; c.lineWidth = 6*scale; c.lineCap = 'round';
      c.beginPath(); c.moveTo(x-sign*29*scale, y+12*scale); c.lineTo(x+sign*29*scale, y-12*scale); c.stroke();
    }
  }
  return canvas;
}
