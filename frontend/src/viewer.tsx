import { Component, Suspense, useEffect, useMemo, useRef, type ReactNode } from 'react';
import { createRoot, events, useFrame, useThree } from '@react-three/fiber';
import { GaesupWorld, GaesupWorldContent, GaesupController, useGaesupStore } from 'gaesup-world';
import { Physics, RigidBody, type RapierRigidBody } from '@react-three/rapier';
import { WebGPURenderer } from 'three/webgpu';
import * as THREE from 'three';
import { GLTFLoader, type GLTF } from 'three/addons/loaders/GLTFLoader.js';

type Model = { gltf: GLTF; url: string };
type ViewProps = { model: Model; animation: number; hidden: Set<number>; onReady(): void; onError(error: Error): void; onWorld(position: { x: number; y: number; z: number }, meshes: number): void };
const worldMode = { type: 'character', controller: 'keyboard', control: 'thirdPerson' } as const;

function release(object: THREE.Object3D) {
  const textures = new Set<THREE.Texture>(), materials = new Set<THREE.Material>(), geometries = new Set<THREE.BufferGeometry>();
  object.traverse(node => {
    if (!(node instanceof THREE.Mesh)) return;
    geometries.add(node.geometry);
    for (const material of Array.isArray(node.material) ? node.material : [node.material]) {
      materials.add(material);
      for (const value of Object.values(material)) if (value instanceof THREE.Texture) textures.add(value);
    }
    if (node instanceof THREE.SkinnedMesh) node.skeleton.dispose();
  });
  textures.forEach(texture => { (texture.source.data as ImageBitmap)?.close?.(); texture.dispose(); });
  materials.forEach(material => material.dispose());
  geometries.forEach(geometry => geometry.dispose());
}

class PreviewBoundary extends Component<{ children: ReactNode; onError(error: Error): void }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch(error: Error) { this.props.onError(error); }
  render() { return this.state.failed ? null : this.props.children; }
}

function CharacterScene({ model, animation, hidden, onReady, onWorld }: ViewProps) {
  const gl = useThree(state => state.gl);
  const body = useRef<RapierRigidBody>(null!);
  const outer = useRef<THREE.Group>(null!);
  const inner = useRef<THREE.Group>(null!);
  const mixer = useMemo(() => new THREE.AnimationMixer(model.gltf.scene), [model]);
  const playing = useRef(-2);
  const ready = useRef(false), sample = useRef(0);
  const bounds = useMemo(() => new THREE.Box3().setFromObject(model.gltf.scene), [model]);
  const size = useMemo(() => bounds.getSize(new THREE.Vector3()), [bounds]);
  const origin = useMemo(() => [-((bounds.min.x + bounds.max.x) / 2), -bounds.min.y, -((bounds.min.z + bounds.max.z) / 2)] as [number, number, number], [bounds]);
  const excluded = useMemo(() => {
    const names: string[] = [];
    model.gltf.scene.traverse(node => { if (node instanceof THREE.Mesh) names.push(node.name); });
    return names;
  }, [model]);
  useEffect(() => {
    model.gltf.scene.traverse(node => {
      const index = model.gltf.parser.associations.get(node)?.nodes;
      if (index !== undefined) node.visible = !hidden.has(index);
    });
  }, [model, hidden]);
  useEffect(() => {
    const canvas = gl.domElement;
    canvas.tabIndex = 0; canvas.setAttribute('aria-label', '개숲월드 캐릭터 이동 영역');
    const activate = () => { canvas.focus(); useGaesupStore.getState().setInteractionActive(true); };
    const deactivate = () => useGaesupStore.getState().setInteractionActive(false);
    canvas.addEventListener('pointerdown', activate); canvas.addEventListener('blur', deactivate);
    deactivate();
    return () => { canvas.removeEventListener('pointerdown', activate); canvas.removeEventListener('blur', deactivate); deactivate(); };
  }, [gl]);
  useEffect(() => {
    return () => { mixer.stopAllAction(); mixer.uncacheRoot(model.gltf.scene); };
  }, [mixer, model]);
  useFrame((_, delta) => {
    if (!body.current || !outer.current) return;
    const velocity = body.current.linvel(), speed = Math.hypot(velocity.x, velocity.z);
    const pattern = speed > 5 ? /run|running/i : speed > .1 ? /walk|walking/i : /idle|standing/i;
    const requested = animation >= 0 ? animation : model.gltf.animations.findIndex(clip => pattern.test(clip.name));
    if (requested !== playing.current) {
      mixer.stopAllAction();
      if (requested >= 0) mixer.clipAction(model.gltf.animations[requested]).reset().play();
      playing.current = requested;
    }
    mixer.update(Math.min(delta, .1));
    if (!ready.current || ++sample.current % 12 === 0) {
      let count = 0;
      model.gltf.scene.traverseVisible(node => { if (node instanceof THREE.Mesh) count++; });
      onWorld(body.current.translation(), count);
      if (!ready.current && count > 0) { ready.current = true; onReady(); }
    }
  });
  return <GaesupController key={model.url} clickToMove={false} position={[0, .12, 0]}
    rigidBodyRef={body} outerGroupRef={outer} innerGroupRef={inner}
    colliderSize={{ height: Math.max(size.y, .3), radius: Math.max(.15, Math.min(size.x, size.z) * .3) }}
    excludeBaseNodes={excluded}>
    <group rotation={[0, Math.PI, 0]}><group position={origin}><primitive object={model.gltf.scene} dispose={null} /></group></group>
  </GaesupController>;
}

function Garden() {
  return <>
    <color attach="background" args={['#dce9e2']} />
    <fog attach="fog" args={['#dce9e2', 18, 48]} />
    <hemisphereLight args={[0xffffff, 0x8b9e85, 2.4]} />
    <directionalLight position={[4, 9, 5]} intensity={3.5} />
    <RigidBody type="fixed" colliders="cuboid">
      <mesh position={[0, -.15, 0]} receiveShadow><boxGeometry args={[24, .3, 24]} /><meshStandardMaterial color="#abc8ae" roughness={.95} /></mesh>
    </RigidBody>
    <gridHelper args={[24, 24, '#8aaa93', '#a1bea5']} position={[0, .005, 0]} />
    {[-1, 1].flatMap(x => [-1, 1].map(z => <group key={`${x}:${z}`} position={[x * 7, 0, z * 7]}>
      <RigidBody type="fixed" colliders="cuboid"><mesh position={[0, .8, 0]}><cylinderGeometry args={[.22, .3, 1.6, 8]} /><meshStandardMaterial color="#958071" /></mesh></RigidBody>
      <mesh position={[0, 2.4, 0]}><icosahedronGeometry args={[1.5, 1]} /><meshStandardMaterial color={x > 0 ? '#739e82' : '#93b58a'} roughness={1} /></mesh>
    </group>))}
  </>;
}

function CharacterViewport(props: ViewProps) {
  const urls = useMemo(() => ({ characterUrl: props.model.url }), [props.model.url]);
  const cameraOption = useMemo(() => {
    const height = Math.max(new THREE.Box3().setFromObject(props.model.gltf.scene).getSize(new THREE.Vector3()).y, 1);
    return { type: 'thirdPerson' as const, xDistance: 0, yDistance: height * 1.35, zDistance: height * 2.8,
      distance: height * 2.8, fov: 42, zoom: 1, enableZoom: true, minZoom: .6, maxZoom: 2, zoomSpeed: .001, enableCollision: false };
  }, [props.model]);
  return <GaesupWorld urls={urls} mode={worldMode} cameraOption={cameraOption} enablePhysics>
    <PreviewBoundary onError={props.onError}>
        <Suspense fallback={null}>
          <Physics gravity={[0, -9.81, 0]}>
            <GaesupWorldContent showGrid={false} showAxes={false}>
              <Garden />
              <CharacterScene {...props} />
            </GaesupWorldContent>
          </Physics>
        </Suspense>
    </PreviewBoundary>
  </GaesupWorld>;
}

/** DOM workspace bridge; React/R3F own the canvas, render loop, camera and model scene. */
export class ModelViewer {
  private root?: ReturnType<typeof createRoot>;
  private mount = document.createElement('div');
  private canvas = document.createElement('canvas');
  private observer: ResizeObserver;
  private initializing?: Promise<void>;
  private badge = document.createElement('span');
  private model: Model | null = null;
  private retired: THREE.Object3D[] = [];
  private animation = -1;
  private hidden = new Set<number>();
  private generation = 0;
  private disposed = false;
  private request?: AbortController;
  private renderers = new Set<WebGPURenderer>();
  private finish?: () => void;
  private fail?: (error: Error) => void;
  constructor(private container: HTMLElement) {
    this.mount.className = 'r3f-viewport'; this.badge.className = 'renderer-badge';
    this.badge.textContent = 'WebGPU 초기화 중';
    container.append(this.mount, this.badge);
    this.mount.append(this.canvas);
    this.observer = new ResizeObserver(() => { if (this.root && !this.disposed) void this.root.configure({ size: this.size() }); });
    this.observer.observe(container);
  }
  private size() { return { width: this.container.clientWidth, height: this.container.clientHeight, top: 0, left: 0 }; }
  private initialize() {
    return this.initializing ??= (async () => {
      const renderer = new WebGPURenderer({ canvas: this.canvas, antialias: true, alpha: true });
      await renderer.init();
      if (this.disposed) { renderer.dispose(); return; }
      this.renderers.add(renderer);
      renderer.outputColorSpace = THREE.SRGBColorSpace;
      renderer.toneMapping = THREE.ACESFilmicToneMapping;
      renderer.setClearColor(0x000000, 0);
      const backend = renderer.backend as { isWebGPUBackend?: boolean };
      this.onBackend(backend.isWebGPUBackend ? 'webgpu' : 'webgl-fallback');
      // Initialize before creating an R3F root so a removed panel cannot finish an async Canvas mount.
      this.root = createRoot(this.canvas);
      await this.root.configure({ gl: renderer, size: this.size(), dpr: Math.min(devicePixelRatio, 2),
        camera: { fov: 42, position: [0, 3, 7] }, events,
        onCreated: state => state.events.connect?.(this.canvas) });
      if (this.disposed) this.root.unmount();
    })();
  }
  private onBackend = (value: string) => {
    if (this.disposed) return;
    this.container.dataset.renderer = value;
    this.badge.textContent = value === 'webgpu' ? 'WebGPU · gaesup-world' : 'WebGL 호환 모드 · gaesup-world';
  };
  private onWorld = (position: { x: number; y: number; z: number }, meshes: number) => {
    this.container.dataset.world = 'gaesup-world';
    this.container.dataset.characterPosition = JSON.stringify(position);
    this.container.dataset.characterMeshes = String(meshes);
  };
  private onReady = () => {
    this.retired.forEach(release); this.retired = [];
    this.finish?.(); this.finish = undefined; this.fail = undefined;
  };
  private onError = (error: Error) => {
    this.container.dataset.renderer = 'error'; this.badge.textContent = '렌더러 오류';
    this.fail?.(new Error(`3D 렌더러 오류: ${error.message}`)); this.fail = undefined; this.finish = undefined;
  };
  private render() {
    if (!this.model || this.disposed || !this.root) return;
    this.root.render(<CharacterViewport model={this.model} animation={this.animation} hidden={this.hidden}
      onReady={this.onReady} onError={this.onError} onWorld={this.onWorld} />);
  }
  async load(url: string) {
    const token = ++this.generation;
    this.request?.abort(); this.finish?.();
    this.request = new AbortController();
    const response = await fetch(url, { signal: this.request.signal });
    if (!response.ok) throw new Error('모델 파일을 불러올 수 없습니다.');
    const content = await response.arrayBuffer();
    const digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', content))).map(value => value.toString(16).padStart(2, '0')).join('');
    const gltf = await new GLTFLoader().parseAsync(content, '');
    if (this.disposed || token !== this.generation) { release(gltf.scene); return []; }
    if (this.model) this.retired.push(this.model.gltf.scene);
    this.model = { gltf, url: `${url}${url.includes('?') ? '&' : '?'}sha256=${digest}` }; this.animation = -1; this.hidden = new Set();
    this.container.dataset.modelSha256 = digest;
    await this.initialize();
    if (this.disposed || token !== this.generation) return [];
    await new Promise<void>((resolve, reject) => { this.finish = resolve; this.fail = reject; this.render(); });
    return gltf.animations.map((clip, index) => ({ index, name: clip.name || `Animation ${index + 1}` }));
  }
  play(index: number) { this.animation = index; this.render(); }
  setVisible(index: number, visible: boolean) {
    this.hidden = new Set(this.hidden);
    if (visible) this.hidden.delete(index); else this.hidden.add(index);
    this.render();
  }
  dispose() {
    this.disposed = true; this.generation++; this.request?.abort(); this.finish?.();
    this.observer.disconnect(); this.root?.unmount();
    // R3F completes its canvas cleanup on a deferred callback; release the WebGPU device afterwards.
    const renderers = this.renderers;
    setTimeout(() => { renderers.forEach(renderer => renderer.dispose()); renderers.clear(); }, 600);
    if (this.model) release(this.model.gltf.scene);
    this.retired.forEach(release); this.retired = [];
    this.mount.remove(); this.badge.remove(); delete this.container.dataset.renderer;
  }
}
