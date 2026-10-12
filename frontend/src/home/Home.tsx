import { useI18n } from '../i18n/I18n.tsx';
import { Logo } from '../components/Logo.tsx';
import { MockSource } from '../sensor/sources/MockSource.ts';
import { SensorProvider, useSensor } from '../state/SensorContext.tsx';
import { ThemeToggle } from '../shell/ThemeToggle.tsx';
import { HelpGuide } from '../shell/HelpGuide.tsx';
import { LanguageSelector } from '../i18n/LanguageSelector.tsx';
import { ScoresWidget } from '../widgets/ScoresWidget.tsx';
import { ScoreTrendWidget } from '../widgets/ScoreTrendWidget.tsx';
import s from './Home.module.css';


const steps = [
  {
    title: 'The radar watches',
    text: 'A small radar tracks how your arm, shoulder and trunk move during an exercise.',
  },
  {
    title: 'AI scores every rep',
    text: 'It rates fatigue, movement quality and compensation, and watches how they change.',
  },
  {
    title: 'You get a next step',
    text: 'Keep going, fix your posture, ease off, rest, or see your physiotherapist.',
  },
];

/** Radar vs the usual alternatives. Keep claims inside what the proposal says. */
const compare = {
  options: ['Camera', 'Wearables', 'Radar'],
  rows: [
    { label: 'Privacy', cells: ['Records your face and room', 'Nothing recorded', 'Sees movement only'] },
    { label: 'Setup', cells: ['Needs good light and framing', 'Straps or patches on the body', 'Nothing to wear'] },
    { label: 'At home', cells: ['Awkward to place', 'Easy to put on wrong', 'Place it once, then exercise'] },
  ],
};

/** Landing page shown first. The dashboard lives at #/app. */
export function Home() {
  const { ui } = useI18n();
  const { connect } = useSensor();
  const tryDemo = () => {
    void connect(new MockSource());
    location.hash = '#/app';
  };
  return ui((
    <div className={s.page}>
      <header className={s.nav}>
        <a className={s.brand} href="#/" aria-label="TrueRehab-RF home">
          <Logo className={s.mark} />
          <span>TrueRehab-RF</span>
        </a>
        <div className={s.navRight}>
          <a className={s.navLink} href="#/app">Dashboard</a>
          <HelpGuide />
          <LanguageSelector />
          <ThemeToggle />
        </div>
      </header>

      <main>
        <section className={s.hero}>
          <h1 className={s.title}>
            See the recovery.
            <span className={s.muted}>Spot the compensation.</span>
          </h1>
          <p className={s.lead}>
            A small radar that tells real recovery from compensating movement during rehab. No cameras. Nothing to wear.
          </p>
          <div className={s.actions}>
            <button type="button" className={`primary ${s.cta}`} onClick={tryDemo}>
              Try the demo
            </button>
            <a className={`${s.cta} ${s.secondary}`} href="#/app">
              Connect a kit
            </a>
          </div>
        </section>

        <section className={s.demo} aria-label="Live demo of the three scores">
          <SensorProvider initialSource={() => new MockSource()}>
            <div className={s.card}>
              <div className={s.cardHead}>
                <span className={s.live}>
                  <span className={s.liveDot} aria-hidden />
                  Live demo
                </span>
                <span className={s.note}>Made-up data, not a measurement</span>
              </div>
              <div className={s.cardBody}>
                <div>
                  <ScoresWidget showDirection={false} />
                </div>
                <div className={s.chart}>
                  <ScoreTrendWidget showLegend windowMs={20_000} />
                </div>
              </div>
            </div>
          </SensorProvider>
        </section>

        <section className={s.section} aria-labelledby="how-title">
          <h2 id="how-title" className={s.sectionTitle}>
            From movement to a clear next step.
          </h2>
          <p className={s.sectionLead}>Three things happen while you exercise. You don’t have to do anything.</p>
          <ol className={s.steps}>
            {steps.map((st, i) => (
              <li key={st.title} className={s.step}>
                <span className={s.stepNum} aria-hidden>
                  {i + 1}
                </span>
                <h3 className={s.stepTitle}>{st.title}</h3>
                <p className={s.stepText}>{st.text}</p>
              </li>
            ))}
          </ol>
        </section>

        <section className={s.section} aria-labelledby="why-title">
          <h2 id="why-title" className={s.sectionTitle}>
            Why radar.
          </h2>
          <p className={s.sectionLead}>
            Rehab works best when it feels easy. Radar keeps the technology out of the way, and it never replaces your
            physiotherapist.
          </p>
          <div className={s.tableWrap}>
            <table className={s.compare}>
              <thead>
                <tr>
                  <td />
                  {compare.options.map((o, i) => (
                    <th key={o} scope="col" className={i === compare.options.length - 1 ? s.ours : undefined}>
                      {o}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {compare.rows.map((r) => (
                  <tr key={r.label}>
                    <th scope="row">{r.label}</th>
                    {r.cells.map((c, i) => (
                      <td key={c} className={i === r.cells.length - 1 ? s.ours : undefined}>
                        {c}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </main>

      <footer className={s.footer}>
        <p>TrueRehab-RF · AEII 2026</p>
        <p>Built to support physiotherapists, not replace them.</p>
      </footer>
    </div>
  ));
}
