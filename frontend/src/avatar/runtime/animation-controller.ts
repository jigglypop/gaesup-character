import { AnimationMixer, type AnimationAction, type AnimationClip, type Object3D } from 'three';

/** Exactly one mixer owned by an avatar; clothing never creates animation players. */
export class AnimationSystem {
  private mixer!: AnimationMixer;
  private actions = new Map<string, AnimationAction>();
  private current?: string;
  constructor(readonly id: string) {}
  initializeMixer(root: Object3D) { this.mixer = new AnimationMixer(root); }
  addAnimation(name: string, clip: AnimationClip) { this.actions.set(name, this.mixer.clipAction(clip)); }
  getAnimationList() { return [...this.actions.keys()]; }
  getCurrentAnimation() { return this.current; }
  getPlayback() {
    const action = this.current ? this.actions.get(this.current) : undefined;
    return { animationTime: action?.time ?? 0, animationDuration: action?.getClip().duration ?? 0 };
  }
  getState() { return { animationMixer: this.mixer, isPlaying: this.current ? this.actions.get(this.current)?.isRunning() : false }; }
  playAnimation(name: string, fade = .15) {
    const next = this.actions.get(name);
    if (!next) throw new Error(`Unknown animation: ${name}`);
    const previous = this.current ? this.actions.get(this.current) : undefined;
    next.reset().setEffectiveTimeScale(1).setEffectiveWeight(1).play();
    if (previous && previous !== next) previous.crossFadeTo(next, fade, false);
    this.current = name;
  }
  updateAnimation(delta: number) { this.mixer.update(Math.min(Math.max(delta, 0), .1)); }
  clearActions() { this.mixer.stopAllAction(); this.actions.clear(); this.current = undefined; }
  dispose() { this.clearActions(); this.mixer.uncacheRoot(this.mixer.getRoot()); }
}
