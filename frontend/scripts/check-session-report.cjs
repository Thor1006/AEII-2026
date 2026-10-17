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
const { loadReportHistory, saveReportHistory, REPORT_HISTORY_KEY } = load('src/state/SessionReportHistory.ts');
const historyStore = new SensorStore();
const originals = [];
for (let i = 1; i <= 6; i++) {
  const active = start(historyStore, `history-${i}`, i * 10000);
  historyStore.ingest(message({ type: 'scores', t: i * 10000 + 100, scores: { fatigue: { value: i / 10 } } }));
  originals.push(stop(historyStore, active, i * 10000 + i * 1000, 0));
  assert.equal(historyStore.reports.records.length, Math.min(i, 5));
}
assert.deepEqual(historyStore.reports.records.map(item => item.session.id), ['history-6', 'history-5', 'history-4', 'history-3', 'history-2']);
const older = historyStore.reports.records[4];
assert.equal(older, originals[1]);
assert.equal(older.durationMs, 2000);
assert.equal(older.scores.find(score => score.key === 'fatigue').mean, .2);
assert.equal(historyStore.reports.latest.durationMs, 6000);
const historySnapshot = JSON.stringify(historyStore.reports.records);
const recordsPointer = historyStore.reports.records;
historyStore.reset();
assert.equal(historyStore.reports.records, recordsPointer);
historyStore.setSession({ ...older.session, state: 'running' }, true);
historyStore.setSession(older.session, false, 0);
assert.equal(historyStore.reports.records, recordsPointer); // Replaying a saved session does not duplicate it.
assert.equal(JSON.stringify(historyStore.reports.records), historySnapshot);
assert.ok(reportCsv(older).includes('"Duration","2","s"')); // Export the selected old snapshot, not the latest.
let stored = null;
const memoryStorage = {
  getItem: key => { assert.equal(key, REPORT_HISTORY_KEY); return stored; },
  setItem: (key, value) => { assert.equal(key, REPORT_HISTORY_KEY); stored = value; },
};
assert.deepEqual(loadReportHistory(() => memoryStorage), { records: [], warning: undefined });
assert.equal(saveReportHistory(historyStore.reports.records, () => memoryStorage), true);
const restored = loadReportHistory(() => memoryStorage);
assert.equal(restored.warning, undefined);
assert.deepEqual(restored.records, historyStore.reports.records);
const reloadedStore = new SensorStore({ reportHistory: restored.records });
assert.deepEqual(reloadedStore.reports.records, historyStore.reports.records);
const seventh = start(reloadedStore, 'history-7', 80000);
stop(reloadedStore, seventh, 81000, 0);
assert.deepEqual(reloadedStore.reports.records.map(item => item.session.id), ['history-7', 'history-6', 'history-5', 'history-4', 'history-3']);
assert.equal(JSON.stringify(historyStore.reports.records), historySnapshot);
assert.equal(saveReportHistory(originals, () => memoryStorage), true);
assert.equal(JSON.parse(stored).records.length, 5);
stored = 'broken JSON';
assert.deepEqual(loadReportHistory(() => memoryStorage), { records: [], warning: 'invalid' });
stored = JSON.stringify({ version: 99, records: restored.records });
assert.equal(loadReportHistory(() => memoryStorage).warning, 'invalid');
const corrupt = JSON.parse(JSON.stringify(older)); corrupt.scores[0].points = [{ t: 10, v: 8, samples: 1 }];
stored = JSON.stringify({ version: 1, records: [corrupt, null, older, older] });
assert.deepEqual(loadReportHistory(() => memoryStorage), { records: [older], warning: 'invalid' });
const denied = () => { throw new Error('Storage denied'); };
assert.deepEqual(loadReportHistory(denied), { records: [], warning: 'unavailable' });
assert.equal(saveReportHistory(restored.records, denied), false);
assert.equal(saveReportHistory(restored.records, () => ({ ...memoryStorage, setItem: () => { throw new Error('Quota exceeded'); } })), false);
assert.equal(JSON.stringify(historyStore.reports.records), historySnapshot);
for (const language of ['en', 'th', 'zh-HK']) {
  const t = createTranslator(language);
  if (language !== 'en') assert.notEqual(t('Saved sessions'), 'Saved sessions');
  assert.ok(!t('Open saved session {number}: {exercise}, {date}', { number: 1, exercise: 'test', date: 'today' }).includes('{number}'));
}
// Deletion changes only the selected snapshot and notifies persistence without a live sensor.
const deletionStore = new SensorStore({ reportHistory: restored.records });
let deleteNotifications = 0;
const unsubscribeDeletion = deletionStore.subscribe(() => deleteNotifications++);
const beforeDelete = deletionStore.reports.records;
const middleReport = beforeDelete[2];
assert.equal(deletionStore.deleteSessionReport({ ...middleReport }), false); // Stale/cloned objects cannot delete another snapshot.
assert.equal(deletionStore.reports.records, beforeDelete);
assert.equal(deleteNotifications, 0);
assert.equal(deletionStore.deleteSessionReport(middleReport), true);
assert.equal(deleteNotifications, 1);
assert.equal(deletionStore.reports.records.length, 4);
assert.equal(deletionStore.reports.latest, beforeDelete[0]);
assert.deepEqual(deletionStore.reports.records, beforeDelete.filter(item => item !== middleReport));
assert.equal(JSON.stringify(beforeDelete), historySnapshot); // Existing snapshots were not mutated.
assert.equal(saveReportHistory(deletionStore.reports.records, () => memoryStorage), true);
assert.deepEqual(loadReportHistory(() => memoryStorage).records, deletionStore.reports.records);
const retainedOldest = deletionStore.reports.records[3];
const fillSlot = start(deletionStore, 'fills-deleted-slot', 90000);
stop(deletionStore, fillSlot, 91000, 0);
assert.equal(deletionStore.reports.records.length, 5);
assert.equal(deletionStore.reports.records[4], retainedOldest); // Filling a freed slot must not evict another record.
const latestBeforeDelete = deletionStore.reports.latest;
const latestAfterDelete = deletionStore.reports.records[1];
assert.equal(deletionStore.deleteSessionReport(latestBeforeDelete), true);
assert.equal(deletionStore.reports.latest, latestAfterDelete);
deletionStore.setSession({ ...latestBeforeDelete.session, state: 'running' }, true);
deletionStore.setSession(latestBeforeDelete.session, false, 0);
assert.equal(deletionStore.reports.records.includes(latestBeforeDelete), false); // A late ack does not resurrect a deleted report.
const activeDuringDelete = start(deletionStore, 'active-during-delete', 92000);
assert.equal(deletionStore.deleteSessionReport(deletionStore.reports.records.at(-1)), true);
deletionStore.ingest(message({ type: 'scores', t: 92100, scores: { fatigue: { value: .7 } } }));
const afterDeleteSession = stop(deletionStore, activeDuringDelete, 93000, 0);
assert.equal(afterDeleteSession.scores.find(score => score.key === 'fatigue').mean, .7);
assert.equal(JSON.stringify(beforeDelete), historySnapshot);
// Reused IDs with different start times are distinct sessions.
const reusedId = start(deletionStore, latestBeforeDelete.session.id, 94000);
const reusedReport = stop(deletionStore, reusedId, 95000, 0);
assert.equal(reusedReport.session.startedAt, 94000);
for (const savedReport of [...deletionStore.reports.records]) assert.equal(deletionStore.deleteSessionReport(savedReport), true);
assert.equal(deletionStore.reports.latest, null);
assert.deepEqual(deletionStore.reports.records, []);
assert.equal(saveReportHistory(deletionStore.reports.records, () => memoryStorage), true);
assert.deepEqual(loadReportHistory(() => memoryStorage), { records: [], warning: undefined });
deletionStore.reset();
assert.equal(deletionStore.reports.records.length, 0);
const afterEmpty = start(deletionStore, 'after-empty', 96000);
stop(deletionStore, afterEmpty, 97000, 0);
assert.equal(deletionStore.reports.records.length, 1);
unsubscribeDeletion();
for (const language of ['th', 'zh-HK']) {
  const t = createTranslator(language);
  for (const key of ['Delete', 'Delete this saved session?', 'Yes, delete', 'Session deleted. A slot is now available.']) assert.notEqual(t(key), key);
}
console.log('PASS: session aggregation, safe localized CSV, five-record history, delete/free-slot behavior, active-session isolation, deletion persistence, late-message protection and storage failures.');
