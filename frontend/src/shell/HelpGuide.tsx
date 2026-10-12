import { useI18n } from '../i18n/I18n.tsx';
import { useEffect, useId, useRef, useState } from 'react';
import { MockSource } from '../sensor/sources/MockSource.ts';
import { useSensor } from '../state/SensorContext.tsx';
import s from './HelpGuide.module.css';

const topics = [
  { key: 'start', label: 'Get started' },
  { key: 'screen', label: 'Read the screen' },
  { key: 'kit', label: 'Use a kit' },
  { key: 'help', label: 'Fix a problem' },
] as const;

type Topic = (typeof topics)[number]['key'];

/** A shared guide for the homepage, connection screen, and dashboard. */
export function HelpGuide() {
  const { ui } = useI18n();
  const { source, state, connect } = useSensor();
  const [open, setOpen] = useState(false);
  const [topic, setTopic] = useState<Topic>('start');
  const [largeText, setLargeText] = useState(() => {
    try { return localStorage.getItem('trf-help-large-text') === 'true'; }
    catch { return false; }
  });
  const dialogRef = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const descriptionId = useId();
  const canTryDemo = !source || state === 'idle' || state === 'closed';

  useEffect(() => {
    try { localStorage.setItem('trf-help-large-text', String(largeText)); }
    catch { /* The guide still works when browser storage is unavailable. */ }
  }, [largeText]);

  useEffect(() => {
    if (!open) return;
    const dialog = dialogRef.current;
    if (!dialog) return;
    const previousOverflow = document.body.style.overflow;
    dialog.showModal();
    document.body.style.overflow = 'hidden';
    return () => {
      if (dialog.open) dialog.close();
      document.body.style.overflow = previousOverflow;
    };
  }, [open]);

  const startDemo = () => {
    setOpen(false);
    void connect(new MockSource());
    location.hash = '#/app';
  };

  return ui((
    <>
      <button type="button" className={s.trigger} aria-haspopup="dialog" onClick={() => { setTopic('start'); setOpen(true); }}>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
          <circle cx="12" cy="12" r="9" />
          <path d="M9.5 9a2.5 2.5 0 0 1 5 0c0 1.7-2.5 2-2.5 4" strokeLinecap="round" />
          <circle cx="12" cy="16.7" r=".7" fill="currentColor" stroke="none" />
        </svg>
        Help &amp; Guide
      </button>

      <dialog
        ref={dialogRef}
        className={`${s.dialog} ${largeText ? s.largeText : ''}`}
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
        onClose={() => setOpen(false)}
        onClick={(event) => { if (event.target === event.currentTarget) setOpen(false); }}
      >
        <header className={s.header}>
          <div>
            <h2 id={titleId}>Help &amp; Guide</h2>
            <p id={descriptionId}>New here? Take it one step at a time.</p>
          </div>
          <button type="button" className={s.close} aria-label="Close guide" autoFocus onClick={() => setOpen(false)}>
            <span aria-hidden="true">×</span> Close
          </button>
        </header>

        <div className={s.body}>
          <div className={s.readingControls}>
            <span>Make this guide easier to read</span>
            <button type="button" className={s.textSize} aria-pressed={largeText} onClick={() => setLargeText(!largeText)}>
              <span aria-hidden="true">Aa</span> Larger text
            </button>
          </div>
          <nav className={s.topics} aria-label="Guide topics">
            {topics.map((item) => (
              <button key={item.key} type="button" aria-pressed={topic === item.key} onClick={() => setTopic(item.key)}>
                {item.label}
              </button>
            ))}
          </nav>

          <section className={s.content} aria-labelledby={`${titleId}-${topic}`}>
            {topic === 'start' && (
              <>
                <h3 id={`${titleId}-start`}>Try the website first</h3>
                <p>You can learn the screen without a radar kit. The demo shows example data.</p>
                <ol className={s.steps}>
                  <li><strong>Choose “Try the demo”.</strong><p>On the homepage, this opens the dashboard. On the connection screen, choose “Start demo”.</p></li>
                  <li><strong>Stay in the “Session” view.</strong><p>Look at the recommendation first, then the repetitions and scores. To practise the session controls, choose “Start session”, then “Start”.</p></li>
                  <li><strong>Open this guide whenever you need it.</strong><p>The Help &amp; Guide button is also at the top of the dashboard. Close the guide to return to your screen.</p></li>
                </ol>
                <p className={s.note}>Demo numbers are made up. You do not need to exercise to explore the demo.</p>
              </>
            )}

            {topic === 'screen' && (
              <>
                <h3 id={`${titleId}-screen`}>What am I looking at?</h3>
                <p>You do not have to understand every chart. Start with the Session view.</p>
                <dl className={s.definitions}>
                  <div><dt>Recommendation</dt><dd>The suggested next step, such as continue, correct posture, or rest.</dd></div>
                  <div><dt>Repetitions (reps)</dt><dd>How many times the exercise movement has been completed.</dd></div>
                  <div><dt>Fatigue</dt><dd>An estimate of how tired the working muscle seems. A lower number is better.</dd></div>
                  <div><dt>Movement quality</dt><dd>How smooth and controlled the movement appears. A higher number is better.</dd></div>
                  <div><dt>Compensation</dt><dd>How much another body part, such as the shoulder or trunk, helps with the movement. A lower number is better.</dd></div>
                  <div><dt>Session and Technical</dt><dd>Session shows the main results. Technical shows radar and connection details, mainly for the project team.</dd></div>
                </dl>
                <p className={s.note}>Read the labels as well as the colours. In demo mode, all scores and suggestions are examples.</p>
              </>
            )}

            {topic === 'kit' && (
              <>
                <h3 id={`${titleId}-kit`}>Connect your radar kit</h3>
                <p>Ask the person setting up the kit for help if you are unsure about its address or key.</p>
                <ol className={s.steps}>
                  <li><strong>Turn on the kit and join the same Wi-Fi.</strong><p>Your computer or tablet and the kit need to be on the same network.</p></li>
                  <li><strong>Open Dashboard and enter the Pi address.</strong><p>Use the address on the kit’s sticker, then choose “Connect”. If asked for a kit key, use the key supplied with that kit.</p></li>
                  <li><strong>Choose “Start session”.</strong><p>Select the exercise, left or right side, and target repetitions. Choose “Start” when you are ready.</p></li>
                  <li><strong>Choose “Stop session” when finished.</strong><p>Select “Yes, stop” to confirm. Opening this guide does not pause or stop an exercise session.</p></li>
                </ol>
                <p className={s.note}>Follow your physiotherapist’s exercise instructions. The current prototype’s simulated scores are for demonstration.</p>
              </>
            )}

            {topic === 'help' && (
              <>
                <h3 id={`${titleId}-help`}>Something not working?</h3>
                <div className={s.questions}>
                  <details><summary>The kit will not connect</summary><p>Check that the kit is on, both devices are on the same Wi-Fi, and the address matches the sticker. If the page asks for a key, check the key too. You can use the demo while someone checks the kit.</p></details>
                  <details><summary>I cannot start a session</summary><p>Connect a kit or start the demo first, then choose “Start session” and “Start”. If a kit says it does not support sessions, ask the project team. A recording plays back an earlier session, so its session controls are off.</p></details>
                  <details><summary>The numbers are not moving</summary><p>Check the connection status at the top of the dashboard. For a recording, check whether playback is paused. If a kit is connected but no data arrives, ask the project team to check the kit.</p></details>
                  <details><summary>The writing is too small</summary><p>Choose “Larger text” above to enlarge this guide. To enlarge the whole website, use your browser’s Zoom setting or press Ctrl and + on Windows, or Command and + on a Mac.</p></details>
                  <details><summary>I do not understand a chart</summary><p>You can stay in the Session view and focus on the recommendation. The small information button beside a panel’s title explains that panel.</p></details>
                </div>
              </>
            )}
          </section>

          <footer className={s.footer}>
            {topic === 'start' && canTryDemo ? (
              <button type="button" className={`primary ${s.action}`} onClick={startDemo}>Try the demo now</button>
            ) : (
              <a href="#/app" className={s.dashboardLink} onClick={() => setOpen(false)}>Go to dashboard</a>
            )}
            <button type="button" className={s.action} onClick={() => setOpen(false)}>Back to my screen</button>
          </footer>
        </div>
      </dialog>
    </>
  ));
}
