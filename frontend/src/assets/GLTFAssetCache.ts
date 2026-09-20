import { GLTFLoader, type GLTF } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { disposeObjectResources } from './gpu-resources';

export type GLTFAssetLease = { gltf: GLTF; release: () => void };
type Entry = { promise: Promise<GLTF>; references: number };

/** Catalog resource ownership shared by imperative consumers. Instances never own source resources. */
export class GLTFAssetCache {
  private entries = new Map<string, Entry>();
  constructor(
    private readonly load: (uri: string) => Promise<GLTF> = (uri) =>
      new GLTFLoader().loadAsync(uri),
  ) {}

  async acquire(uri: string): Promise<GLTFAssetLease> {
    let entry = this.entries.get(uri);
    if (!entry) {
      entry = { promise: Promise.resolve().then(() => this.load(uri)), references: 0 };
      this.entries.set(uri, entry);
    }
    const owned = entry;
    owned.references++;
    let gltf: GLTF;
    try {
      gltf = await owned.promise;
    } catch (error) {
      owned.references--;
      if (this.entries.get(uri) === owned) this.entries.delete(uri);
      throw error;
    }
    let released = false;
    return {
      gltf,
      release: () => {
        if (released) return;
        released = true;
        if (--owned.references > 0) return;
        if (this.entries.get(uri) === owned) this.entries.delete(uri);
        disposeObjectResources(gltf.scenes);
      },
    };
  }
  getReferenceCount(uri: string): number {
    return this.entries.get(uri)?.references ?? 0;
  }
}

export const gltfAssetCache = new GLTFAssetCache();
