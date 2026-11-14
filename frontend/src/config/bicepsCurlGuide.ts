/** Canonical UI copy shared by the guide and the five-language content checks. */
export const bicepsCurlGuide = {
  label: 'Biceps curl',
  title: 'How to do a biceps curl',
  intro: 'Bend at the elbows while keeping your upper arms mostly still.',
  steps: [
    { title: 'Stand tall.', body: 'Keep your upper arms beside your body and your shoulders relaxed.' },
    { title: 'Bend your elbows.', body: 'Lift the dumbbells toward your shoulders without moving your upper arms forward.' },
    { title: 'Stop before your elbows move forward.', body: 'You do not need to reach shoulder height. Stop at the highest position you can control with your upper arms still.' },
    { title: 'Lower slowly.', body: 'Lower the dumbbells with control until your arms are almost straight, then repeat.' },
    { title: 'Keep your body steady.', body: 'Do not swing your torso, push with your legs, or shrug your shoulders.' },
  ],
  reminder: 'Upper arms still. Curl up. Lower slowly. No swinging or shrugging.',
  safety: 'General guidance only. For rehabilitation, use the weight and movement range recommended by your physiotherapist.',
} as const;
