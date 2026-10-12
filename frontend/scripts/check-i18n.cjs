// Run with: node scripts/check-i18n.cjs (uses existing TypeScript and React dependencies).
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const ts = require('typescript');
const React = require('react');
const cache = new Map();
function load(file) {
  file = path.resolve(__dirname, '..', file);
  if (cache.has(file)) return cache.get(file).exports;
  const mod = new Module(file); cache.set(file, mod);
  mod.require = (id) => id.startsWith('.') ? load(path.resolve(path.dirname(file), id)) : require(id);
  mod._compile(ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
  }).outputText, file);
  return mod.exports;
}
const { catalog } = load('src/i18n/catalog.ts');
const { dictionaries, createTranslator } = load('src/i18n/messages.ts');
const { localizeUi } = load('src/i18n/I18n.tsx');
const placeholders = (text) => [...text.matchAll(/\{(\w+)\}/g)].map((match) => match[1]).sort();
assert.deepEqual(Object.keys(dictionaries.en), Object.keys(dictionaries.th));
assert.deepEqual(Object.keys(dictionaries.en), Object.keys(dictionaries['zh-HK']));
for (const [key, translations] of Object.entries(catalog)) {
  for (const text of translations) {
    assert.ok(text.trim(), `Empty translation: ${key}`);
    assert.deepEqual(placeholders(text), placeholders(key), `Placeholder mismatch: ${key}`);
  }
}
const t = createTranslator('zh-HK');
assert.equal(createTranslator('en')('Start session'), 'Start session');
assert.equal(createTranslator('th')('Start session'), 'เริ่มเซสชัน');
assert.equal(t('Start session'), '開始訓練');
assert.equal(t('Rep 7 done · ROM 85°'), '第 7 次動作完成 · ROM 85°');
assert.equal(t('Cannot reach ws://kit.local:8765'), '無法連接 ws://kit.local:8765');
assert.equal(t('Connection lost. Retrying in 1.5 s'), '連接中斷，將於 1.5 s 後重試');
assert.equal(t('Replay Continue'), '重播 Continue');
assert.equal(t('Fatigue: 62%'), '疲勞程度：62%');
assert.equal(t('20.0 of 20'), '20.0／20');
assert.equal(t('Last session: Elbow flexion (bicep curl), 1:25.'), '上次訓練：屈肘運動（二頭肌彎舉），1:25。');
assert.equal(t('DCA1000EVM · 77 GHz · 1.35 m · 0.2 m/s'), 'DCA1000EVM · 77 GHz · 1.35 m · 0.2 m/s');
assert.equal(t('Patient note: felt better today'), 'Patient note: felt better today');
assert.equal(t('constructor'), 'constructor');
assert.equal(t('{constructor}'), '{constructor}');
assert.equal(createTranslator('en')('{constructor}'), '{constructor}');
const onChange = () => {};
const ref = React.createRef();
const input = localizeUi(React.createElement('input', { value: 'My session', onChange, ref, placeholder: 'Pi address' }), t);
assert.equal(input.props.value, 'My session'); assert.equal(input.props.onChange, onChange); assert.equal(input.ref, ref);
assert.equal(input.props.placeholder, 'Pi 地址');
const option = localizeUi(React.createElement('option', null, 'Light'), t);
assert.equal(option.props.children, '淺色'); assert.equal(option.props.value, 'Light');
const code = localizeUi(React.createElement('code', null, 'Start session'), t);
assert.equal(code.props.children, 'Start session');
const userNote = localizeUi(React.createElement('span', { translate: 'no' }, 'Rest'), t);
assert.equal(userNote.props.children, 'Rest');
const siblings = [React.createElement('input', { key: 'patient', value: 'S001', onChange }), React.createElement('button', null, 'Start')];
const chineseSiblings = localizeUi(siblings, t);
const thaiSiblings = localizeUi(siblings, createTranslator('th'));
assert.equal(chineseSiblings[0].key, 'patient');
assert.equal(chineseSiblings[1].key, thaiSiblings[1].key);
assert.equal(chineseSiblings[0].props.value, 'S001');
const intentionalText = new Set(['TrueRehab-RF', 'TrueRehab-RF · AEII 2026', 'Aa', 's', 'ms', '°', '%', '/s', '.local', 'RMS', 'sEMG RMS']);
function checkUiText(directory) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const filename = path.join(directory, entry.name);
    if (entry.isDirectory()) { checkUiText(filename); continue; }
    if (!filename.endsWith('.tsx')) continue;
    const source = ts.createSourceFile(filename, fs.readFileSync(filename, 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
    function visit(node) {
      if (ts.isJsxText(node)) {
        const text = node.text.replace(/\s+/g, ' ').trim().replaceAll('&amp;', '&');
        const parent = node.parent;
        const tag = ts.isJsxElement(parent) ? parent.openingElement.tagName.getText(source) : '';
        if (/[A-Za-z]/.test(text) && tag !== 'code' && tag !== 'pre' && !intentionalText.has(text)) {
          assert.ok(Object.hasOwn(catalog, text), `Untranslated JSX text in ${filename}: ${text}`);
        }
      }
      ts.forEachChild(node, visit);
    }
    visit(source);
  }
}
checkUiText(path.resolve(__dirname, '../src'));
console.log(`PASS: ${Object.keys(catalog).length} translation pairs, UI copy coverage, placeholders, dynamic messages, stable React keys, and unchanged input values/events/refs/units.`);
