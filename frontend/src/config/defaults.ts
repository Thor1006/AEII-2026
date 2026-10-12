/**
 * Fallback labels and display rules, used when the Pi doesn't describe itself
 * (protocol v1) or leaves something out. A Pi that sends `hello` overrides these.
 * Edit to rename things, translate the UI (e.g. into Thai) or change thresholds.
 */
import type { RecommendationStyle } from '../components/RecommendationCard.tsx';

export interface ScoreDef {
  key: string;
  label: string;
  higherIsWorse: boolean;
  /** [warn, bad] on the badness scale, 0–1. */
  thresholds?: [number, number];
  color?: string;
  /** Shown in the ⓘ explainer. */
  description?: string;
}

export const scoreDefs: ScoreDef[] = [
  { key: 'fatigue', label: 'Fatigue', higherIsWorse: true, color: 'var(--series-1)', description: 'How tired the working muscle seems. Lower is better.' },
  { key: 'quality', label: 'Movement quality', higherIsWorse: false, color: 'var(--series-2)', description: 'Smoothness and range of the movement. Higher is better.' },
  { key: 'compensation', label: 'Compensation', higherIsWorse: true, color: 'var(--series-3)', description: 'How much other body parts (trunk, shoulder) are helping. Lower is better.' },
];

export const recommendationStyles: Record<string, RecommendationStyle> = {
  continue: { label: 'Continue', hint: 'Form looks good. Keep going.', tone: 'good', icon: '●' },
  correct_posture: { label: 'Correct posture', hint: 'Sit upright and keep the shoulder down.', tone: 'warn', icon: '▲' },
  reduce_load: { label: 'Reduce load or range', hint: 'Use a lighter weight or a smaller range.', tone: 'warn', icon: '▼' },
  rest: { label: 'Rest', hint: 'Take a break before the next set.', tone: 'bad', icon: '■' },
  see_physio: { label: 'See your physiotherapist', hint: 'The pattern keeps coming back. Get it checked.', tone: 'bad', icon: '✚' },
};

export const eventTones: Record<string, 'good' | 'warn' | 'bad' | 'info'> = {
  rep_end: 'good',
  compensation: 'bad',
  recommendation: 'info',
  session_start: 'info',
  session_end: 'info',
  marker: 'warn',
};

/** Names for aux channels when the Pi doesn't send a manifest. */
export const auxChannelLabels: Record<string, string> = {
  elbow_angle_deg: 'Elbow angle (°)',
  emg_rms: 'sEMG RMS',
  force_n: 'Force (N)',
};

export const viewTitles: Record<string, string> = {
  range_doppler: 'Range–Doppler',
  micro_doppler: 'Micro-Doppler',
  range_time: 'Range–time',
  range_azimuth: 'Range–azimuth',
};

/** Choices in the "Start session" form. The key is what the Pi receives. */
export const exercises: { key: string; label: string }[] = [
  { key: 'elbow_flexion', label: 'Elbow flexion (bicep curl)' },
  { key: 'shoulder_flexion', label: 'Shoulder flexion' },
  { key: 'shoulder_abduction', label: 'Shoulder abduction' },
  { key: 'other', label: 'Other' },
];

/** Plain-language explainers for the ⓘ button on each panel. */
export const panelHelp = {
  recommendation: 'What the system suggests right now, based on the last rep. It supports the physiotherapist. It does not replace them.',
  reps: 'Repetitions counted from the radar in this session, and the elbow’s range of motion (ROM). A shrinking ROM is an early sign of fatigue.',
  scores: 'Three AI scores from 0 to 100%. Green is fine, yellow is borderline, red needs attention. Fatigue and compensation: lower is better. Quality: higher is better.',
  trend: 'How the scores changed over the last minute. A rising fatigue line usually comes before compensation.',
  radar: 'Each bright spot is something reflecting the radar. Up/down = distance from the radar. Left/right = speed toward (right) or away (left). A moving arm makes a spot that swings sideways.',
  aux: 'Signals from the reference sensors (sEMG on the muscle, force sensor, joint angle). They are used to check the radar during development. The final product won’t need them.',
  events: 'Everything that happened, newest first: reps, compensation alerts, recommendations and your markers.',
  health: 'Every data stream the Pi promised to send, and whether it is arriving. If something is red, the matching panel will be empty.',
  link: 'Raw numbers about the connection, for troubleshooting.',
} as const;
