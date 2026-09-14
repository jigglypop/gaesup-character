import { useEffect, useRef } from 'react';
import { createRoot, events, extend, useFrame, useThree } from '@react-three/fiber';
import { GaesupWorld } from 'gaesup-world';
import * as THREE from 'three';
import { WebGPURenderer } from 'three/webgpu';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { Avatar } from './react';
import type { AvatarRuntime } from './runtime/AvatarRuntime';
import type { AvatarState } from './core/types';

extend(THREE as unknown as Parameters<typeof extend>[0]);

function Orbit() {
  const { camera, gl } = useThree();
  const controls = useRef<OrbitControls | null>(null);
  useEffect(() => {
    const orbit = new OrbitControls(camera, gl.domElement);
    orbit.target.set(0, .9, 0); orbit.enableDamping = true;
    orbit.minDistance = 1.8; orbit.maxDistance = 7; orbit.update(); controls.current = orbit;
    const reset = () => { camera.position.set(2.3, 1.6, 3.5); orbit.target.set(0, .9, 0); orbit.update(); };
    const container = gl.domElement.parentElement;
    container?.addEventListener('avatar:reset-view', reset);
    return () => { container?.removeEventListener('avatar:reset-view', reset); controls.current = null; orbit.dispose(); };
  }, [camera, gl]);
  useFrame(() => controls.current?.update());
  return null;
}

type Props = { initial: AvatarState; onReady(avatar: AvatarRuntime): void; onError(error: Error): void; onBackend(value: string): void };

export function AvatarViewport({ initial, onReady, onError, onBackend }: Props) {
  const mount = useRef<HTMLDivElement>(null);
  const callbacks = useRef({ onReady, onError, onBackend });
  callbacks.current = { onReady, onError, onBackend };
  useEffect(() => {
    const container = mount.current!;
    const canvas = document.createElement('canvas'); container.append(canvas);
    canvas.setAttribute('aria-label', '모듈형 아바타 3D 미리보기');
    let disposed = false, root: ReturnType<typeof createRoot> | undefined;
    const renderer = new WebGPURenderer({ canvas, antialias: true });
    const size = () => ({ width: container.clientWidth, height: container.clientHeight, top: 0, left: 0 });
    const resize = new ResizeObserver(() => { if (root && !disposed) void root.configure({ size: size() }); });
    resize.observe(container);
    void (async () => {
      await renderer.init();
      if (disposed) { renderer.dispose(); return; }
      renderer.outputColorSpace = THREE.SRGBColorSpace;
      renderer.toneMapping = THREE.ACESFilmicToneMapping;
      const backend = (renderer.backend as { isWebGPUBackend?: boolean }).isWebGPUBackend ? 'webgpu' : 'webgl-fallback';
      callbacks.current.onBackend(backend); container.dataset.renderer = backend;
      root = createRoot(canvas);
      await root.configure({ gl: renderer, size: size(), dpr: Math.min(devicePixelRatio, 2), events,
        camera: { fov: 38, position: [2.3, 1.6, 3.5] }, onCreated: state => state.events.connect?.(canvas) });
      if (disposed) return;
      root.render(<GaesupWorld enablePhysics={false}>
        <color attach="background" args={['#191f17']} />
        <hemisphereLight args={['#ffffff', '#8d9a82', 2.5]} />
        <directionalLight position={[3, 5, 4]} intensity={3} />
        <directionalLight position={[-3, 2, -2]} intensity={1.5} />
        <mesh position={[0, -.065, 0]}><cylinderGeometry args={[1.06, 1.09, .12, 64]} /><meshStandardMaterial color="#394730" roughness={.9} /></mesh>
        <gridHelper args={[14, 28, '#38492c', '#252f1e']} position={[0, -.13, 0]} />
        <Orbit />
        <Avatar avatarId="atelier-avatar" body={initial.body} equipment={initial.equipment} animation="idle"
          onReady={avatar => callbacks.current.onReady(avatar)} onError={error => callbacks.current.onError(error)} />
      </GaesupWorld>);
    })().catch(error => { if (!disposed) callbacks.current.onError(error instanceof Error ? error : new Error(String(error))); });
    return () => {
      disposed = true; resize.disconnect(); root?.unmount();
      setTimeout(() => renderer.dispose(), 600); canvas.remove();
    };
  }, [initial]);
  return <div className="avatar-viewport" ref={mount} data-world="gaesup-world" />;
}
