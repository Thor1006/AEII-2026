import type { RecommendationStatus, TelemetryFrame, TrendPoint } from './types';

// Hand-designed presentation anchors. No measurements or trained model are implied.
const anchors: Record<number, [number, number, number, number]> = {
  0: [95, .08, .03, .08], 1: [94, .12, .05, .10], 3: [92, .24, .08, .19],
  5: [86, .42, .12, .38], 6: [83, .52, .17, .54], 7: [78, .61, .23, .75],
  8: [72, .70, .34, .82], 9: [63, .79, .52, .91], 10: [58, .86, .64, .96],
};

export function demoIndices(rep: number): [number, number, number, number] {
  const selected = Math.max(0, Math.min(10, rep));
  if (anchors[selected]) return anchors[selected];
  const lower = Math.max(...Object.keys(anchors).map(Number).filter(index => index < selected));
  const upper = Math.min(...Object.keys(anchors).map(Number).filter(index => index > selected));
  const fraction = (selected - lower) / (upper - lower);
  const a = anchors[lower], b = anchors[upper];
  return [Math.round(a[0] + (b[0] - a[0]) * fraction), ...([1, 2, 3].map(index => a[index] + (b[index] - a[index]) * fraction) as [number, number, number])];
}

export function trendPoint(rep: number): TrendPoint {
  const [movement_quality, fatigue_estimate, compensation_level, compensation_risk] = demoIndices(rep);
  return { rep, movement_quality, fatigue_estimate, compensation_level, compensation_risk };
}

export function recommendationFor(rep: number): TelemetryFrame['recommendation'] {
  const content: Record<RecommendationStatus, { title: string; message: string }> = {
    continue: { title: 'CONTINUE', message: 'The simulated movement remains stable. Maintain the current controlled form.' },
    monitor: { title: 'MONITOR FATIGUE', message: 'The estimated fatigue trend is rising. Maintain controlled movement and watch shoulder position.' },
    correct_form: { title: 'CORRECT FORM', message: 'Simulated future compensation risk is increasing. Slow the curl and keep the elbow close to the torso.' },
    rest: { title: 'REST / CORRECT FORM', message: 'High simulated fatigue and compensation are present. Consider reducing resistance or taking a short rest.' },
  };
  const status: RecommendationStatus = rep >= 9 ? 'rest' : rep >= 7 ? 'correct_form' : rep >= 4 ? 'monitor' : 'continue';
  return { status, ...content[status] };
}

export function syntheticRadar(elapsed: number) {
  const phase = 2 * Math.PI * elapsed / 3;
  const signal = Math.max(0, Math.min(1, .5 - .5 * Math.cos(phase) + .012 * Math.sin(phase * 2.1)));
  const velocity = .16 * Math.PI / 3 * Math.sin(phase);
  return { signal, velocity, range: 1.35 + .16 * (signal - .5), strength: .78 + .05 * Math.sin(phase * .4), phase: velocity >= 0 ? 'Concentric' as const : 'Eccentric' as const };
}

export function syntheticHeatmap(elapsed: number, range: number, velocity: number): number[][] {
  const centerX = (range - .6) / 1.5 * 27;
  const centerY = (velocity + .3) / .6 * 17;
  return Array.from({ length: 18 }, (_, row) => Array.from({ length: 28 }, (_, column) => {
    const target = Math.exp(-(((column - centerX) / 2.2) ** 2 + ((row - centerY) / 2) ** 2) / 2);
    const lobe = .25 * Math.exp(-(((column - centerX - 4) / 3.8) ** 2 + ((row - centerY + 2) / 2.6) ** 2) / 2);
    const texture = .045 + .02 * Math.sin(column * 1.9 + row * 2.7 + elapsed * .8);
    return Math.round(Math.max(0, Math.min(1, target + lobe + texture)) * 1000) / 1000;
  }));
}
