import type { CSSProperties } from 'react';
import type { AvatarSlot } from '../avatar/core/types';

export function StudioIcon({ name, size = 20 }: { name: string; size?: number }) {
  const paths: Record<string, string> = {
    cube: 'M12 3 3 8v9l9 5 9-5V8l-9-5Zm0 0v9m-9-4 9 5 9-5m-9 5v9',
    grid: 'M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z',
    layers: 'm3 7 9-5 9 5-9 5-9-5Zm0 5 9 5 9-5M3 17l9 5 9-5',
    activity: 'M3 12h4l3-8 4 16 3-8h4',
    arrow: 'M5 12h14m-6-6 6 6-6 6',
    refresh: 'M20 7V3l-4 1M20 7a9 9 0 1 0 1 8',
    focus: 'M3 8V3h5m8 0h5v5M3 16v5h5m8 0h5v-5M8 12h8m-4-4v8',
    download: 'M12 3v12m-5-5 5 5 5-5M4 17v4h16v-4',
    check: 'm5 12 4 4L20 5',
    close: 'm5 5 14 14M5 19 19 5',
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name] || paths.cube} /></svg>;
}

/** Slot illustrations identify catalog entries; the central viewport displays the real GLB. */
export function PieceIcon({ slot, color }: { slot: AvatarSlot; color?: string }) {
  const styles = { '--piece-color': color ?? '#aab19b' } as CSSProperties;
  const shapes: Partial<Record<AvatarSlot, string>> = {
    hair: 'M20 39C15 14 27 8 42 10c19-8 32 4 29 29l-5 18-8-19c-14 4-24-9-24-9l-5 30-10-12Z',
    top: 'm28 19-17 13 11 16 10-6-3 31h35l-3-31 10 6 11-16-18-13c-9 9-25 9-36 0Z',
    bottom: 'M26 17h39l4 59H50l-4-38-4 38H23Z',
    onepiece: 'm32 15-13 11 10 18-12 33h59L63 44l10-18-13-11c-7 8-19 8-28 0Z',
    shoes: 'M17 28h23l1 19 11 9 18 3 4 13H15V55Z',
    hat: 'M24 44 29 22q18-9 35 0l5 22 12 10q-36 19-70 0Z',
    bag: 'M30 29v-7q17-14 30 0v7m-37 0h45l5 45H18Z',
    hand: 'm48 13 15 3-14 45-11-4Zm-15 44 20 7-4 8-21-7Zm4 12-6 16',
    body: 'M37 12q10-8 20 0v16L69 44l-9 6-7-10v19l11 20H49l-4-13-3 13H27l12-21V40l-8 10-9-6 15-16Z',
  };
  return <svg className="piece-symbol" style={styles} viewBox="0 0 92 92" fill="var(--piece-color)" stroke="rgba(255,255,255,.22)" strokeWidth="1.2" strokeLinejoin="round" aria-hidden="true"><path d={shapes[slot] || shapes.body} /></svg>;
}
