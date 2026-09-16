/** Non-destructive image editor: keep source bitmap, crop/mask only the preview/export. */
export type ImageLayer = { slot: string; label: string; asset: string | null; crop: [number, number, number, number]; placement: [number, number, number, number]; visible: boolean; opacity: number; order: number; background: 'alpha' | 'border-gray'; status: string; description?: string };
export type Blueprint = { revision: string; character_id: string; source_url: string | null; source_sha256: string | null; canvas: [number, number]; profile: string; layers: ImageLayer[]; anchors: Record<string, [number, number]>; overlap: Record<string, number>; visual_approval: string };
const cache = new Map<string, Promise<HTMLCanvasElement>>();

export function layerBitmap(layer: ImageLayer): Promise<HTMLCanvasElement> {
  const key = JSON.stringify([layer.asset, layer.crop, layer.background]);
  let result = cache.get(key);
  if (!result) {
    result = new Promise<HTMLCanvasElement>((resolve, reject) => {
      const img = new Image(); img.onload = () => {
        try {
          const [x, y, w, h] = layer.crop;
          const canvas = document.createElement('canvas'); canvas.width = Math.max(1, Math.round(img.width*w)); canvas.height = Math.max(1, Math.round(img.height*h));
          const ctx = canvas.getContext('2d', { willReadFrequently: true })!;
          ctx.drawImage(img, img.width*x, img.height*y, img.width*w, img.height*h, 0, 0, canvas.width, canvas.height);
          if (layer.background === 'border-gray') {
            // Flood only neutral border-connected background, keeping enclosed gray fabric.
            // It is a candidate mask and is explicitly reviewable in the editor.
            const image = ctx.getImageData(0, 0, canvas.width, canvas.height), data = image.data;
            const visited = new Uint8Array(canvas.width*canvas.height), queue = new Int32Array(visited.length); let start = 0, end = 0;
            const add = (i: number) => {
              if (visited[i]) return; visited[i] = 1;
              const r = data[i*4]!, g = data[i*4+1]!, b = data[i*4+2]!;
              if (Math.max(r,g,b)-Math.min(r,g,b) < 24 && r+g+b > 195) queue[end++] = i;
            };
            for (let x=0;x<canvas.width;x++) { add(x); add((canvas.height-1)*canvas.width+x); }
            for (let y=0;y<canvas.height;y++) { add(y*canvas.width); add(y*canvas.width+canvas.width-1); }
            while (start<end) {
              const i=queue[start++]!; data[i*4+3]=0;
              if(i%canvas.width) add(i-1); if(i%canvas.width<canvas.width-1)add(i+1);
              if(i>=canvas.width)add(i-canvas.width); if(i<visited.length-canvas.width)add(i+canvas.width);
            }
            ctx.putImageData(image,0,0);
          }
          const data=ctx.getImageData(0,0,canvas.width,canvas.height).data;
          let left=canvas.width,top=canvas.height,right=0,bottom=0;
          for(let y=0;y<canvas.height;y++)for(let x=0;x<canvas.width;x++)if(data[(y*canvas.width+x)*4+3]!>20){left=Math.min(left,x);top=Math.min(top,y);right=Math.max(right,x);bottom=Math.max(bottom,y);}
          if(right<left)throw new Error('배경 마스크가 파츠를 모두 지웠습니다. 원본 알파 모드로 확인하세요.');
          const trimmed=document.createElement('canvas');trimmed.width=right-left+1;trimmed.height=bottom-top+1;
          trimmed.getContext('2d')!.drawImage(canvas,left,top,trimmed.width,trimmed.height,0,0,trimmed.width,trimmed.height);
          resolve(trimmed);
        } catch(error) {reject(error);}
      };
      img.onerror=()=>reject(new Error('파츠 이미지를 불러오지 못했습니다.'));
      img.src=`/api/avatar-blueprints/assets/${encodeURIComponent(layer.asset!)}`;
    });
    cache.set(key,result); result.catch(()=>cache.delete(key));
    if(cache.size>40)cache.delete(cache.keys().next().value!);
  }
  return result;
}

export function downloadCanvas(canvas: HTMLCanvasElement, filename: string) {
  const link=document.createElement('a');link.download=filename;link.href=canvas.toDataURL('image/png');link.click();
}
