/**
 * Colormaps as 256-entry RGB lookup tables (Uint8ClampedArray, length 768).
 * Add your own with `registerColormap`.
 */
export type Colormap = Uint8ClampedArray;

type Vec3 = [number, number, number];

/** Polynomial fit (Matt Zucker's approximations of the matplotlib maps). */
function polyMap(coeffs: Vec3[]): Colormap {
  const lut = new Uint8ClampedArray(256 * 3);
  for (let i = 0; i < 256; i++) {
    const t = i / 255;
    for (let ch = 0; ch < 3; ch++) {
      let v = 0;
      for (let k = coeffs.length - 1; k >= 0; k--) v = v * t + coeffs[k][ch];
      lut[i * 3 + ch] = Math.round(Math.min(1, Math.max(0, v)) * 255);
    }
  }
  return lut;
}

function gradient(stops: string[]): Colormap {
  const rgb = stops.map((hex) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16)));
  const lut = new Uint8ClampedArray(256 * 3);
  for (let i = 0; i < 256; i++) {
    const x = (i / 255) * (rgb.length - 1);
    const j = Math.min(rgb.length - 2, Math.floor(x));
    const f = x - j;
    for (let ch = 0; ch < 3; ch++) lut[i * 3 + ch] = rgb[j][ch] + (rgb[j + 1][ch] - rgb[j][ch]) * f;
  }
  return lut;
}

const viridis = polyMap([
  [0.2777273272234177, 0.005407344544966578, 0.3340998053353061],
  [0.1050930431085774, 1.404613529898575, 1.384590162594685],
  [-0.3308618287255563, 0.214847559468213, 0.09509516302823659],
  [-4.634230498983486, -5.799100973351585, -19.33244095627987],
  [6.228269936347081, 14.17993336680509, 56.69055260068105],
  [4.776384997670288, -13.74514537774601, -65.35303263337234],
  [-5.435455855934631, 4.645852612178535, 26.3124352495832],
]);

const inferno = polyMap([
  [0.0002189403691192265, 0.001651004631001012, -0.01948089843709184],
  [0.1065134194856116, 0.5639564367884091, 3.932712388889277],
  [11.60249308247187, -3.972853965665698, -15.9423941062914],
  [-41.70399613139459, 17.43639888205313, 44.35414519872813],
  [77.162935699427, -33.40235894210092, -81.80730925738993],
  [-71.31942824499214, 32.62606426397723, 73.20951985803202],
  [25.13112622477341, -12.24266895238567, -23.07032500287172],
]);

const colormaps: Record<string, Colormap> = {
  viridis,
  inferno,
  gray: gradient(['#000000', '#ffffff']),
  ice: gradient(['#06121f', '#0b3b5c', '#1d7a8c', '#7fd1c7', '#f2fbf9']),
};

export type ColormapName = 'viridis' | 'inferno' | 'gray' | 'ice' | (string & {});

export function getColormap(name: ColormapName | Colormap): Colormap {
  if (typeof name !== 'string') return name;
  return colormaps[name] ?? viridis;
}

export function registerColormap(name: string, lutOrStops: Colormap | string[]): void {
  colormaps[name] = Array.isArray(lutOrStops) ? gradient(lutOrStops) : lutOrStops;
}

export function colormapNames(): string[] {
  return Object.keys(colormaps);
}

/** CSS linear-gradient for legends. */
export function colormapCss(name: ColormapName | Colormap, direction = 'to top'): string {
  const lut = getColormap(name);
  const stops = [0, 64, 128, 192, 255].map((i) => `rgb(${lut[i * 3]},${lut[i * 3 + 1]},${lut[i * 3 + 2]})`);
  return `linear-gradient(${direction}, ${stops.join(',')})`;
}
