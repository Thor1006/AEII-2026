import type { RefObject } from 'react';
import { useEffect, useState } from 'react';

export interface CanvasSize {
  width: number;
  height: number;
  dpr: number;
}

/** Tracks an element's CSS size and sizes the canvas backing store for sharp drawing. */
export function useCanvasSize(
  containerRef: RefObject<HTMLElement | null>,
  canvasRef: RefObject<HTMLCanvasElement | null>,
): CanvasSize {
  const [size, setSize] = useState<CanvasSize>({ width: 0, height: 0, dpr: 1 });
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      const dpr = window.devicePixelRatio || 1;
      const canvas = canvasRef.current;
      if (canvas) {
        canvas.width = Math.max(1, Math.round(width * dpr));
        canvas.height = Math.max(1, Math.round(height * dpr));
      }
      setSize({ width, height, dpr });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [containerRef, canvasRef]);
  return size;
}

/** Resolve "var(--token)" (or any CSS color) to a value canvas understands. */
export function cssColor(el: Element, value: string): string {
  const m = /^var\((--[^),]+)(?:,\s*(.+))?\)$/.exec(value.trim());
  if (!m) return value;
  return getComputedStyle(el).getPropertyValue(m[1]).trim() || m[2] || '#888';
}
