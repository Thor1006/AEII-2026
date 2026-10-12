import { useI18n } from '../i18n/I18n.tsx';
import type { FormEvent } from 'react';
import { useRef, useState } from 'react';
import { displayAddress, forgetAddress, normalizePiAddress, recentAddresses } from '../lib/address.ts';
import { cleanKey, forgetKey, getKey, saveKey } from '../lib/keystore.ts';
import { MockSource } from '../sensor/sources/MockSource.ts';
import { ReplaySource } from '../sensor/sources/ReplaySource.ts';
import { primarySourceKinds, sourceRegistry } from '../sensor/sources/index.ts';
import { WebSocketSource } from '../sensor/sources/WebSocketSource.ts';
import { useNow, useSensor } from '../state/SensorContext.tsx';
import { ConnectionHelp } from './ConnectionHelp.tsx';
import { SourceForm } from './SourceForm.tsx';
import s from './StartScreen.module.css';

/** Shown when nothing is connected, or while the first connection is being made. */
export function StartScreen() {
  const { ui } = useI18n();
  const { source, state, error } = useSensor();
  const pending = source && state !== 'closed' && state !== 'idle';
  return ui((
    <div className={s.screen}>
      <div className={s.intro}>
        <h2>Connect to your TrueRehab kit</h2>
        <p>The kit’s radar watches the exercise and this page shows the results live. Pick where the data comes from.</p>
      </div>
      {pending ? <Connecting /> : <Choices />}
      {!pending && source instanceof WebSocketSource && source.authProblem && state === 'closed' && <KeyPrompt source={source} />}
      {!pending && error && state === 'closed' && !(source instanceof WebSocketSource && source.authProblem) && <p className={s.error}>{error}</p>}
    </div>
  ));
}

/** Shown when the kit's key was missing or wrong. */
function KeyPrompt({ source }: { source: WebSocketSource }) {
  const { ui } = useI18n();
  const { connect } = useSensor();
  const [value, setValue] = useState('');
  const [err, setErr] = useState<string>();
  const problem = source.authProblem;
  const askForKey = problem === 'needs-key' || problem === 'wrong-key';

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const key = cleanKey(value);
    if (!key) {
      setErr('A kit key is 64 letters and numbers (0 to 9 and a to f). Copy it from the kit’s sticker.');
      return;
    }
    saveKey(source.url, key);
    void connect(new WebSocketSource({ url: source.url, key }));
  };

  return ui((
    <form className={s.keyBox} onSubmit={submit} role="alert">
      <h3>{askForKey ? 'Enter the kit key' : 'Can’t trust this kit'}</h3>
      <p>{source.error}</p>
      {askForKey && (
        <>
          <label className={s.field}>
            <span>Kit key</span>
            <input
              value={value}
              onChange={(e) => {
                setValue(e.target.value);
                setErr(undefined);
              }}
              placeholder="64 letters and numbers from the sticker"
              autoCapitalize="off"
              autoCorrect="off"
              autoComplete="off"
              spellCheck={false}
              type="password"
            />
          </label>
          {err && <p className={s.error}>{err}</p>}
          <button type="submit" className="primary">
            Connect with this key
          </button>
        </>
      )}
      {problem === 'no-key-on-kit' && (
        <button
          type="button"
          onClick={() => {
            forgetKey(source.url);
            void connect(new WebSocketSource({ url: source.url }));
          }}
        >
          Forget the saved key and connect anyway
        </button>
      )}
    </form>
  ));
}

function Choices() {
  const { ui } = useI18n();
  const { connect } = useSensor();
  const [recent, setRecent] = useState(recentAddresses);
  const [address, setAddress] = useState(() => (recent[0] ? displayAddress(recent[0]) : ''));
  const [err, setErr] = useState<string>();
  const fileRef = useRef<HTMLInputElement>(null);
  const extra = sourceRegistry.filter((d) => !primarySourceKinds.includes(d.kind));

  const connectPi = (input: string) => {
    const url = normalizePiAddress(input);
    if (!url) {
      setErr('That doesn’t look like an address. Try something like trh-kit-01.local or 192.168.1.20');
      return;
    }
    setErr(undefined);
    void connect(new WebSocketSource({ url, key: getKey(url) }));
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    connectPi(address);
  };

  return ui((
    <>
      <div className={s.cards}>
        <form className={`${s.card} ${s.primary}`} onSubmit={onSubmit}>
          <div className={s.cardIcon} aria-hidden>
            ◉
          </div>
          <h3>Raspberry Pi kit</h3>
          <p>Live data from a kit on the same Wi-Fi.</p>
          <label className={s.field}>
            <span>Pi address</span>
            <input
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              placeholder="trh-kit-01.local"
              autoCapitalize="off"
              autoCorrect="off"
              spellCheck={false}
              inputMode="url"
            />
          </label>
          {recent.length > 0 && (
            <div className={s.recent}>
              <span>Recent:</span>
              {recent.map((u) => (
                <span key={u} className={s.chip}>
                  <button type="button" onClick={() => connectPi(u)}>
                    {displayAddress(u)}
                  </button>
                  <button
                    type="button"
                    aria-label={`Forget ${displayAddress(u)}`}
                    className={s.chipX}
                    onClick={() => {
                      forgetAddress(u);
                      setRecent(recentAddresses());
                    }}
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
          )}
          {err && <p className={s.error}>{err}</p>}
          <button type="submit" className="primary">
            Connect
          </button>
          <p className={s.hint}>The address is on the kit’s sticker. If you open the address the Pi shows (http://…:8080), it connects by itself.</p>
        </form>

        <div className={s.card}>
          <div className={s.cardIcon} aria-hidden>
            ▶
          </div>
          <h3>Try the demo</h3>
          <p>Made-up data that behaves like a real kit. Good for learning the screen. Not a measurement.</p>
          <button type="button" onClick={() => void connect(new MockSource())}>
            Start demo
          </button>
        </div>

        <div className={s.card}>
          <div className={s.cardIcon} aria-hidden>
            ⏏
          </div>
          <h3>Open a recording</h3>
          <p>Replay a session saved earlier with the Record button (.ndjson file).</p>
          <input
            ref={fileRef}
            type="file"
            accept=".ndjson,.jsonl,.json"
            hidden
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) void connect(new ReplaySource({ file }));
              e.target.value = '';
            }}
          />
          <button type="button" onClick={() => fileRef.current?.click()}>
            Choose file…
          </button>
        </div>
      </div>

      {extra.length > 0 && (
        <details className={s.more}>
          <summary>More options</summary>
          {extra.map((d) => (
            <SourceForm key={d.kind} def={d} />
          ))}
        </details>
      )}
    </>
  ));
}

function Connecting() {
  const { ui } = useI18n();
  const { source, state, error, disconnect, connect } = useSensor();
  useNow(1000); // attempt count lives on the source; refresh it
  if (!source) return null;
  const isPi = source instanceof WebSocketSource;
  const attempts = isPi ? source.attempts : 0;
  const failed = state === 'error' || attempts > 0;
  const title = isPi
    ? attempts > 0
      ? `Can’t reach ${displayAddress(source.url)} yet`
      : `Connecting to ${displayAddress(source.url)}…`
    : state === 'error'
      ? 'Couldn’t open this source'
      : 'Opening…';

  return ui((
    <div className={s.connecting} role="status" aria-live="polite">
      <div className={s.connHead}>
        {!failed || isPi ? <span className={s.spinner} aria-hidden /> : null}
        <div>
          <h3>{title}</h3>
          {isPi && attempts > 0 && (
            <p className={s.muted}>
              Tried {attempts} {attempts === 1 ? 'time' : 'times'}. Still trying in the background. Check these:
            </p>
          )}
          {!isPi && error && <p className={s.error}>{error}</p>}
        </div>
      </div>
      {isPi && attempts > 0 && <ConnectionHelp source={source} state={state} error={error} />}
      <div className={s.row}>
        <button type="button" onClick={disconnect}>
          {failed ? 'Back' : 'Cancel'}
        </button>
        {isPi && attempts > 0 && (
          <button type="button" onClick={() => void connect(new MockSource())}>
            Use demo data instead
          </button>
        )}
      </div>
    </div>
  ));
}
