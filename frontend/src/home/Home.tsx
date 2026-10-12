import { Logo } from '../components/Logo.tsx';
import { MockSource } from '../sensor/sources/MockSource.ts';
import { SensorProvider, useSensor } from '../state/SensorContext.tsx';
import { ThemeToggle } from '../shell/ThemeToggle.tsx';
import { ScoresWidget } from '../widgets/ScoresWidget.tsx';
import { ScoreTrendWidget } from '../widgets/ScoreTrendWidget.tsx';
import s from './Home.module.css';

/** Landing page shown first. The dashboard lives at #/app. */
export function Home() {
  const { connect } = useSensor();
  const tryDemo = () => {
    void connect(new MockSource());
    location.hash = '#/app';
  };
  return (
    <div className={s.page}>
      <header className={s.nav}>
        <a className={s.brand} href="#/" aria-label="TrueRehab-RF home">
          <Logo className={s.mark} />
          <span>TrueRehab-RF</span>
        </a>
        <div className={s.navRight}>
          <a className={s.navLink} href="#/app">Dashboard</a>
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

        <section className={s.showcase} aria-labelledby="preview-title">
          <h2 id="preview-title" className={s.sectionTitle}>
            Three scores. One clear picture.
          </h2>
          <p className={s.sectionLead}>Fatigue, movement quality and compensation, updated as the exercise happens.</p>
          <SensorProvider initialSource={() => new MockSource()}>
            <div className={s.card}>
              <div className={s.cardHead}>
                <span className={s.live}>Live demo</span>
                <span className={s.note}>Made-up data, not a measurement</span>
              </div>
              <div className={s.cardBody}>
                <div className={s.gauges}>
                  <ScoresWidget showDirection={false} />
                </div>
                <div className={s.chart}>
                  <ScoreTrendWidget showLegend windowMs={20_000} />
                </div>
              </div>
            </div>
          </SensorProvider>
        </section>
      </main>

      <footer className={s.footer}>
        <p>TrueRehab-RF · AEII 2026</p>
        <p>Built to support physiotherapists, not replace them.</p>
      </footer>
    </div>
  );
}
