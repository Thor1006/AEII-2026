const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const ts = require('typescript');
const cache = new Map();
function load(file) {
  file = path.resolve(__dirname, '..', file);
  if (cache.has(file)) return cache.get(file).exports;
  const mod = new Module(file); cache.set(file, mod);
  mod.require = id => id.startsWith('.') ? load(path.resolve(path.dirname(file), id)) : require(id);
  mod._compile(ts.transpileModule(fs.readFileSync(file, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText, file);
  return mod.exports;
}
const { SensorStore } = load('src/state/SensorStore.ts');
const { reportCsv } = load('src/state/SessionReport.ts');
const { createTranslator } = load('src/i18n/messages.ts');
let seq = 0;
function message(body) { return { v: 1, seq: seq++, src: 'test', t: 1000, ...body }; }
function start(store, id = 'S1', t = 1000) {
  const session = { id, state: 'running', startedAt: t, exercise: 'elbow_flexion', side: 'right', targetReps: 12 };
  store.ingest(message({ type: 'event', kind: 'session_start', t, data: { session } }));
  return session;
}
function stop(store, session, t, reps) {
  store.ingest(message({ type: 'event', kind: 'session_end', t, data: { session: { ...session, state: 'stopped', endedAt: t }, reps } }));
  return store.reports.latest;
}
const store = new SensorStore({ historyLength: 2, eventLength: 2 });
const session = start(store);
store.ingest(message({ type: 'scores', t: 999, scores: { fatigue: { value: 1 } } }));
store.ingest(message({ type: 'scores', t: 1001, sessionId: 'OTHER', scores: { fatigue: { value: 1 } } }));
for (let i = 0; i < 10000; i++) {
  store.ingest(message({ type: 'scores', t: 1001 + i, sessionId: 'S1', scores: { fatigue: { value: i % 2 ? .6 : .2 } } }));
  if (i % 10 === 0) {
    const rep = message({ type: 'event', kind: 'rep_end', t: 1001 + i, data: { rep: i / 10 + 1 } });
    store.ingest(rep); store.ingest(rep);
    store.ingest(message({ ...rep, seq }));
  }
}
const report = stop(store, session, 12000, 1000);
const metric = report.scores.find(score => score.key === 'fatigue');
assert.equal(report.reps, 1000);
assert.equal(report.observedReps, 1000);
assert.equal(metric.samples, 10000);
assert.ok(Math.abs(metric.mean - .4) < 1e-10);
assert.equal(metric.first, .2); assert.equal(metric.last, .6);
assert.equal(report.durationMs, 11000);
assert.equal(report.partial, false);
assert.ok(metric.points.length <= 240);
assert.equal(metric.points.reduce((n,point) => n + point.samples, 0), 10000);
assert.equal(store.scores.get('fatigue').size, 2);
assert.equal(store.events.size, 2);
const snapshot = JSON.stringify(report);
store.ingest(message({ type: 'scores', t: 13000, scores: { fatigue: { value: 1 } } }));
store.setSession({ ...session, state: 'stopped', endedAt: 12000 }, false, 1000);
assert.equal(store.reports.latest, report); assert.equal(JSON.stringify(report), snapshot);
store.setSession(session, true); // A late start ack must not reopen a finished report.
store.ingest(message({ type: 'scores', t: 13500, scores: { fatigue: { value: 1 } } }));
store.setSession({ ...session, state: 'stopped', endedAt: 12000 }, false, 1000);
assert.equal(store.reports.latest, report);
store.reset(); assert.equal(store.reports.latest, report);
const next = start(store, 'S2', 14000);
const empty = stop(store, next, 15000, 0);
assert.equal(empty.reps, 0); assert.equal(empty.scores[0].mean, null);
assert.equal(empty.scores[0].first, null); assert.equal(JSON.stringify(report), snapshot);
const unfinished = new SensorStore(); const unfinishedSession = start(unfinished);
unfinished.ingest(message({ type: 'event', kind: 'rep_end', t: 1200, data: { rep: 1 } }));
const unfinishedReport = stop(unfinished, unfinishedSession, 1400, 2);
assert.equal(unfinishedReport.reps, 1); assert.equal(unfinishedReport.reportedReps, 2);
assert.equal(unfinishedReport.partial, false);
const unknown = new SensorStore(); const unknownSession = start(unknown);
unknown.ingest(message({ type: 'scores', t: 1200, scores: { custom_score: { value: .8 } } }));
assert.equal(stop(unknown, unknownSession, 1400).scores.find(score => score.key === 'custom_score').directionKnown, false);
const late = new SensorStore();
late.setSession({ id: 'late', state: 'running', startedAt: 1000 });
const partial = stop(late, late.session, 2000);
assert.equal(partial.partial, true); assert.equal(partial.reps, null);
const invalid = new SensorStore(); const invalidSession = start(invalid);
invalid.ingest(message({ type: 'scores', t: 1100, scores: { fatigue: { value: NaN }, quality: { value: 5 } } }));
invalid.setSession(invalidSession, true); // An ack must not erase a data-quality warning.
assert.equal(stop(invalid, invalidSession, 2000, 0).partial, true);
const lost = new SensorStore(); const lostSession = start(lost);
lost.ingest(message({ type: 'scores', seq: seq++ + 10, t: 1200, scores: { fatigue: { value: .2 } } }));
assert.equal(stop(lost, lostSession, 2000, 0).partial, true);
const csv = reportCsv({ ...report, session: { ...report.session, userId: '  =1+1' }, device: 'A,"B"\nC' });
assert.ok(csv.startsWith('\uFEFF'));
assert.ok(csv.includes('"\'  =1+1"'));
assert.ok(csv.includes('"A,""B""\nC"'));
assert.ok(csv.includes('"Duration","11","s"'));
const invalidTime = new SensorStore(); const invalidTimeSession = start(invalidTime);
const invalidTimeReport = stop(invalidTime, invalidTimeSession, 1e100, 0);
assert.equal(invalidTimeReport.durationMs, null);
assert.doesNotThrow(() => reportCsv(invalidTimeReport));
const duplicateScores = new SensorStore(); const duplicateSession = start(duplicateScores);
const duplicateScore = message({ type: 'scores', t: 1100, scores: { fatigue: { value: .5 } } });
duplicateScores.ingest(duplicateScore); duplicateScores.ingest(duplicateScore);
assert.equal(stop(duplicateScores, duplicateSession, 1200, 0).scores[0].samples, 1);
for (const language of ['en', 'th', 'zh-HK']) {
  const t = createTranslator(language);
  assert.ok(reportCsv(report,t).includes(`"${t('Completed reps')}"`));
  assert.notEqual(language === 'en' ? 'translated' : t('Session summary'), 'Session summary');
}
console.log('PASS: complete long-session totals, bounded trends, duplicate/out-of-session filtering, frozen reports, missing/invalid data, loss warnings, resets and localized safe CSV.');
