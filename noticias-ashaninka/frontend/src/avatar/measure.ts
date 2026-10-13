// Medición de la boca RENDERIZADA (tarea 3.8): apertura a partir de los píxeles del canvas.
//
// Es independiente del modelo: se calibra solo. Se dibuja el avatar con la boca en reposo y
// luego con cada visema vocálico al 100 %; los píxeles que cambian forman la máscara de la boca.
// La apertura en un instante es la diferencia absoluta media con el reposo dentro de la máscara,
// normalizada por la diferencia de la forma más abierta (aa), de modo que 1 = boca abierta.

import type { AvatarViewer } from "./viewer";

export interface MouthCalibration {
  width: number;
  height: number;
  mask: Uint8Array;
  neutral: Uint8ClampedArray;
  maskPixels: number;
  ref: number;
}

const VOWELS = ["aa", "ih", "ou", "ee", "oh"];

function snapshot(canvas: HTMLCanvasElement, scratch: HTMLCanvasElement): Uint8ClampedArray {
  scratch.width = canvas.width;
  scratch.height = canvas.height;
  const ctx = scratch.getContext("2d", { willReadFrequently: true }) as CanvasRenderingContext2D;
  ctx.drawImage(canvas, 0, 0);
  return ctx.getImageData(0, 0, canvas.width, canvas.height).data;
}

function grayDiff(a: Uint8ClampedArray, b: Uint8ClampedArray, i: number): number {
  const p = i * 4;
  return (Math.abs(a[p] - b[p]) + Math.abs(a[p + 1] - b[p + 1]) + Math.abs(a[p + 2] - b[p + 2])) / 3;
}

export function calibrateMouth(viewer: AvatarViewer, canvas: HTMLCanvasElement, threshold = 10): MouthCalibration {
  const scratch = document.createElement("canvas");
  viewer.renderExpressions({});
  const neutral = new Uint8ClampedArray(snapshot(canvas, scratch));
  const n = canvas.width * canvas.height;
  const mask = new Uint8Array(n);
  for (const v of VOWELS) {
    viewer.renderExpressions({ [v]: 1 });
    const s = snapshot(canvas, scratch);
    for (let i = 0; i < n; i++) if (grayDiff(s, neutral, i) > threshold) mask[i] = 1;
  }
  let maskPixels = 0;
  for (let i = 0; i < n; i++) maskPixels += mask[i];
  const cal: MouthCalibration = {
    width: canvas.width,
    height: canvas.height,
    mask,
    neutral,
    maskPixels,
    ref: 1,
  };
  viewer.renderExpressions({ aa: 1 });
  cal.ref = rawOpenness(cal, snapshot(canvas, scratch)) || 1;
  return cal;
}

function rawOpenness(cal: MouthCalibration, frame: Uint8ClampedArray): number {
  let sum = 0;
  for (let i = 0; i < cal.mask.length; i++) if (cal.mask[i]) sum += grayDiff(frame, cal.neutral, i);
  return cal.maskPixels ? sum / cal.maskPixels : 0;
}

export function mouthOpenness(cal: MouthCalibration, canvas: HTMLCanvasElement, scratch: HTMLCanvasElement): number {
  return rawOpenness(cal, snapshot(canvas, scratch)) / cal.ref;
}

export interface CaptureResult {
  signal: number[];
  frames: string[];
}

/** Dibuja cada instante de `times` y mide la boca; devuelve JPEG de los índices múltiplos de `every`. */
export function captureSignal(
  viewer: AvatarViewer,
  canvas: HTMLCanvasElement,
  cal: MouthCalibration,
  times: number[],
  firstIndex: number,
  every = 0,
): CaptureResult {
  const scratch = document.createElement("canvas");
  const signal: number[] = [];
  const frames: string[] = [];
  times.forEach((t, k) => {
    viewer.renderAt(t);
    signal.push(mouthOpenness(cal, canvas, scratch));
    if (every > 0 && (firstIndex + k) % every === 0) frames.push(canvas.toDataURL("image/jpeg", 0.92));
  });
  return { signal, frames };
}
