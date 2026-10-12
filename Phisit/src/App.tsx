import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import {
  Activity, ArrowRight, CheckCircle2, CircleHelp, Download, FlaskConical,
  Info, Maximize2, Pause, Play, Radar, RotateCcw, Save, Settings2,
  ShieldCheck, Square, Waves, X,
} from 'lucide-react';
import {
  CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts';
import { BrowserDemoSource } from './telemetry/browserSource';
import { createTelemetrySource } from './telemetry';
import type { TelemetryFrame, TelemetrySource } from './telemetry/types';

const DEMO_THRESHOLDS = {
  quality: { excellent: 90, good: 75, moderate: 60 },
  fatigue: { low: .30, moderate: .60, high: .80 },
  compensation: { low: .20, moderate: .40 },
  risk: { low: .30, moderate: .60, high: .80 },
};

const percent = (value: number) => `${Math.round(value * 100)}%`;
const formatTime = (seconds: number) => {
  const total = Math.floor(seconds);
  return `${String(Math.floor(total / 3600)).padStart(2, '0')}:${String(Math.floor(total / 60) % 60).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`;
};
const qualityLabel = (value: number) => value >= DEMO_THRESHOLDS.quality.excellent ? 'EXCELLENT' : value >= DEMO_THRESHOLDS.quality.good ? 'GOOD' : value >= DEMO_THRESHOLDS.quality.moderate ? 'MODERATE' : 'POOR';
const fatigueLabel = (value: number) => value <= DEMO_THRESHOLDS.fatigue.low ? 'LOW' : value <= DEMO_THRESHOLDS.fatigue.moderate ? 'MODERATE' : value <= DEMO_THRESHOLDS.fatigue.high ? 'HIGH' : 'VERY HIGH';
const compensationLabel = (value: number) => value < DEMO_THRESHOLDS.compensation.low ? 'LOW' : value < DEMO_THRESHOLDS.compensation.moderate ? 'MODERATE' : 'ELEVATED';
const riskLabel = (value: number) => value < DEMO_THRESHOLDS.risk.low ? 'LOW RISK' : value < DEMO_THRESHOLDS.risk.moderate ? 'MODERATE RISK' : value < DEMO_THRESHOLDS.risk.high ? 'HIGH RISK' : 'VERY HIGH RISK';

function Tag({ children, tone = 'blue' }: { children: ReactNode; tone?: 'blue' | 'teal' | 'amber' | 'red' }) {
  return <span className={`tag tag-${tone}`}>{children}</span>;
}

function SectionTitle({ eyebrow, title, note }: { eyebrow: string; title: string; note?: string }) {
  return <div className="section-title"><div><span className="eyebrow">{eyebrow}</span><h2>{title}</h2></div>{note && <span className="section-note">{note}</span>}</div>;
}

function MetricCard({ label, value, suffix, caption, tone, prominent = false }: {
  label: string; value: string | number; suffix?: string; caption: string;
  tone: 'teal' | 'amber' | 'orange' | 'red' | 'blue'; prominent?: boolean;
}) {
  return <div className={`metric-card metric-${tone} ${prominent ? 'prominent' : ''}`}><div className="metric-label">{label}</div><div className="metric-number">{value}<small>{suffix}</small></div><div className="metric-caption"><span className="metric-pin"/>{caption}</div></div>;
}

function RadarIllustration({ frame }: { frame: TelemetryFrame }) {
  const signal = frame.movement.normalized_signal;
  const wristY = 132 + (1 - signal) * 61;
  const compensation = frame.ai.compensation_level >= .4;
  return <div className="radar-illustration"><div className="visual-toolbar"><span><i className="live-dot"/> CONTACTLESS RADAR FIELD <em>· SIMULATED</em></span><span>77 GHz CLASS <b>·</b> {frame.radar.range_m.toFixed(2)} m</span></div>
    <svg viewBox="0 0 620 300" role="img" aria-label="Illustration of mmWave radar monitoring a person doing a standing biceps curl without a camera">
      <defs><linearGradient id="beam" x1="0" y1="0" x2="1" y2="0"><stop stopColor="#1677B8" stopOpacity=".21"/><stop offset="1" stopColor="#16A6A0" stopOpacity=".03"/></linearGradient><radialGradient id="halo"><stop stopColor="#16A6A0" stopOpacity=".15"/><stop offset="1" stopColor="#16A6A0" stopOpacity="0"/></radialGradient></defs>
      <g className="visual-grid">{Array.from({ length: 13 }, (_, i) => <line key={`v${i}`} x1={i * 52} x2={i * 52} y1="0" y2="300"/>)}{Array.from({ length: 7 }, (_, i) => <line key={`h${i}`} y1={i * 50} y2={i * 50} x1="0" x2="620"/>)}</g>
      <ellipse cx="430" cy="146" rx="162" ry="138" fill="url(#halo)"/>
      <path d="M100 229 L402 35 L402 268 Z" fill="url(#beam)"/>
      <g className="radar-waves"><path d="M115 205 Q155 230 115 255"/><path d="M137 181 Q218 230 137 280"/><path d="M175 158 Q295 230 175 302"/><path d="M210 139 Q365 230 210 319"/></g>
      <path d="M27 262 H590" className="ground-line"/>
      <g className="radar-device"><path d="M65 231 L92 231 L99 262 L58 262 Z"/><rect x="58" y="187" width="41" height="44" rx="7"/><circle cx="78.5" cy="209" r="10"/><circle cx="78.5" cy="209" r="3"/></g>
      <text x="45" y="281" className="svg-caption">AWR1843BOOST</text>
      <g className="patient"><circle cx="441" cy="47" r="20" className="patient-head"/><path d="M421 82 Q441 76 460 84 L469 179 Q441 188 414 177 Z" className="patient-torso"/><path d="M427 180 L414 253 M454 180 L467 253 M416 252 L432 253 M456 253 L478 253" className="patient-leg"/><path d="M459 94 L480 154 L492 199" className="patient-other-arm"/><path d={`M419 92 L396 163 L${438 - signal * 8} ${wristY}`} className="target-arm"/><circle cx="419" cy="92" r="6" className={compensation ? 'joint-risk' : 'joint-normal'}/><circle cx="396" cy="163" r="6" className="joint-target"/><circle cx={438 - signal * 8} cy={wristY} r="6" className="joint-target"/><path d={`M${425 - signal * 8} ${wristY} H${451 - signal * 8} M${429 - signal * 8} ${wristY - 11} V${wristY + 11} M${447 - signal * 8} ${wristY - 11} V${wristY + 11}`} className="dumbbell"/></g>
      <path d="M419 92 L354 74 H318 M396 163 L332 177 H305 M446 153 L515 177 H552" className="label-lines"/>
      <text x="266" y="69" className="svg-label">SHOULDER</text><text x="275" y="194" className="svg-label">ELBOW</text><text x="555" y="182" className="svg-label">TRUNK</text>
      <path d="M111 263 H394" className="measure-line"/><text x="207" y="256" className="svg-measure">≈ 1–2 m / NO CAMERA</text>
    </svg>
    <div className="visual-legend"><span><i className="legend-dot teal"/> Target arm</span><span><i className="legend-dot blue"/> Radar waves</span><span><i className="legend-dot red"/> Compensation cue</span></div>
  </div>;
}

function StatusStrip({ frame }: { frame: TelemetryFrame }) {
  const entries = [
    ['RADAR', 'AWR1843BOOST', frame.system.radar],
    ['DATA CAPTURE', 'DCA1000EVM', frame.system.capture],
    ['AI ENGINE', 'NO TRAINED MODEL', 'AI SIMULATION'],
    ['SESSION TIME', formatTime(frame.session_seconds), frame.running ? 'STREAMING' : 'READY'],
  ];
  return <div className="status-strip">{entries.map(([label, value, state]) => <div className="status-item" key={label}><span>{label}</span><strong>{value}</strong><small><i className={frame.running && label === 'SESSION TIME' ? 'live-dot' : 'status-dot'}/>{state}</small></div>)}</div>;
}

function SessionControls({ frame, busy, onStart, onStop, onReset, onExport, onSave, onCalibration }: {
  frame: TelemetryFrame; busy: boolean; onStart: () => void; onStop: () => void;
  onReset: () => void; onExport: () => void; onSave: () => void; onCalibration: () => void;
}) {
  return <div className="controls"><div className="control-field"><span>EXERCISE PROTOCOL</span><select aria-label="Exercise" defaultValue="biceps_curl"><option value="biceps_curl">Biceps Curl / Elbow Flexion</option><option disabled>Shoulder Flexion — Coming Soon</option><option disabled>Knee Extension — Coming Soon</option><option disabled>Sit-to-Stand — Coming Soon</option></select></div><div className="control-field subject"><span>SUBJECT</span><strong>{frame.subject_id}</strong></div><div className="control-field calibration"><span>CALIBRATION</span><button onClick={onCalibration} title="Calibration is a future research feature">NOT CALIBRATED <CircleHelp size={13}/></button></div><div className="control-buttons"><button className="button primary" onClick={onStart} disabled={busy || frame.running}><Play size={14} fill="currentColor"/> START</button><button className="button" onClick={onStop} disabled={busy || !frame.running}><Square size={13} fill="currentColor"/> STOP</button><button className="button icon" aria-label="Reset session" title="Reset session" onClick={onReset} disabled={busy}><RotateCcw size={16}/></button><span className="control-divider"/><button className="button ghost export-button" onClick={onExport} disabled={busy || frame.debug.radar_frames_received === 0}><Download size={15}/> EXPORT CSV</button><button className="button ghost save-button" onClick={onSave} disabled={busy || frame.debug.radar_frames_received === 0}><Save size={15}/> SAVE</button></div></div>;
}

function TimelineChart({ frame }: { frame: TelemetryFrame }) {
  const data = useMemo(() => frame.trend_history.map(point => ({
    rep: `R${point.rep}`, fatigue: Math.round(point.fatigue_estimate * 100),
    compensation: Math.round(point.compensation_level * 100), risk: Math.round(point.compensation_risk * 100),
  })), [frame.trend_history]);
  return <section className="panel timeline-panel" id="timeline"><div className="panel-heading"><div><span className="eyebrow">TEMPORAL AI · DEMONSTRATION</span><h2>Fatigue & compensation timeline</h2><p>Predicted risk rises before visible compensation in this simulated story.</p></div><Tag tone="amber">AI OUTPUTS SIMULATED</Tag></div><div className="chart-legend"><span><i className="legend-dot amber"/> Estimated fatigue</span><span><i className="legend-dot red"/> Compensation level · now</span><span><i className="legend-dot blue"/> Compensation risk · next</span></div><div className="timeline-chart"><ResponsiveContainer width="100%" height="100%"><LineChart data={data} margin={{ top: 11, right: 16, bottom: 3, left: -18 }}><CartesianGrid vertical={false} stroke="#20394e" strokeDasharray="3 5"/><XAxis dataKey="rep" tickLine={false} axisLine={false} stroke="#7790a2" fontSize={11}/><YAxis domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} tickLine={false} axisLine={false} stroke="#7790a2" fontSize={11}/><Tooltip contentStyle={{ background: '#10283d', border: '1px solid #365870', borderRadius: 9, color: '#f4f7fb' }} formatter={value => `${value}%`}/>{data.length > 0 && <ReferenceLine x={data.at(-1)?.rep} stroke="#668c9f" strokeDasharray="4 4"/>}<Line type="monotone" dataKey="fatigue" name="Estimated fatigue" stroke="#F5AE49" strokeWidth={3} dot={{ r: 3, fill: '#F5AE49' }} activeDot={{ r: 5 }} isAnimationActive={false}/><Line type="monotone" dataKey="risk" name="Future compensation risk" stroke="#4DB9E3" strokeWidth={3} dot={{ r: 3, fill: '#4DB9E3' }} activeDot={{ r: 5 }} isAnimationActive={false}/><Line type="monotone" dataKey="compensation" name="Current compensation level" stroke="#E45756" strokeWidth={3} dot={{ r: 3, fill: '#E45756' }} activeDot={{ r: 5 }} isAnimationActive={false}/></LineChart></ResponsiveContainer></div><div className="chart-footnote">Demo indices only · not calibrated clinical measurements</div></section>;
}

function MovementSignal({ frame }: { frame: TelemetryFrame }) {
  const data = useMemo(() => frame.signal_history.map(point => ({ time: point.time_s.toFixed(1), movement: point.value })), [frame.signal_history]);
  return <section className="panel signal-panel" id="signal"><div className="panel-heading compact"><div><span className="eyebrow">SYNTHETIC PERIODIC SIGNAL</span><h2>Movement signal</h2></div><span className="signal-frequency"><Waves size={14}/> PEAK-DETECTED REPS</span></div><div className="signal-chart"><ResponsiveContainer width="100%" height="100%"><LineChart data={data} margin={{ top: 8, right: 9, bottom: 1, left: -23 }}><CartesianGrid vertical={false} stroke="#20394e" strokeDasharray="3 5"/><XAxis dataKey="time" minTickGap={36} tickLine={false} axisLine={false} stroke="#7790a2" fontSize={10}/><YAxis domain={[0, 1]} ticks={[0, .5, 1]} tickLine={false} axisLine={false} stroke="#7790a2" fontSize={10}/><Tooltip contentStyle={{ background: '#10283d', border: '1px solid #365870', borderRadius: 9, color: '#f4f7fb' }} formatter={value => Number(value).toFixed(2)} labelFormatter={label => `${label} s`}/><Line type="monotone" dataKey="movement" name="Normalized movement" stroke="#4bd0c4" strokeWidth={2.5} dot={false} isAnimationActive={false}/></LineChart></ResponsiveContainer></div><div className="panel-bottom"><span>TIME (s)</span><span>NORMALIZED MOVEMENT · REPLACEABLE RADAR FEATURE</span></div></section>;
}

function RangeDopplerMap({ frame }: { frame: TelemetryFrame }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = canvasRef.current;
    const context = canvas?.getContext('2d');
    if (!canvas || !context) return;
    const map = frame.range_doppler;
    if (!map.length || !map[0]?.length) return;
    const left = 38, top = 10, width = canvas.width - 50, height = canvas.height - 39;
    context.fillStyle = '#091c2d'; context.fillRect(0, 0, canvas.width, canvas.height);
    const cellWidth = width / map[0].length, cellHeight = height / map.length;
    map.forEach((row, y) => row.forEach((value, x) => {
      const intensity = Math.min(1, value);
      const hue = intensity < .35 ? 212 - intensity * 90 : intensity < .7 ? 180 - (intensity - .35) * 180 : 48 - (intensity - .7) * 85;
      const lightness = 11 + intensity * 51;
      context.fillStyle = `hsl(${hue} 83% ${lightness}%)`;
      context.fillRect(left + x * cellWidth, top + (map.length - 1 - y) * cellHeight, Math.ceil(cellWidth), Math.ceil(cellHeight));
    }));
    context.strokeStyle = '#4b6c83'; context.lineWidth = 1;
    context.beginPath(); context.moveTo(left, top); context.lineTo(left, top + height); context.lineTo(left + width, top + height); context.stroke();
    context.fillStyle = '#8aa8b9'; context.font = '11px DM Sans, sans-serif';
    context.fillText('0.6', left, top + height + 18); context.fillText('2.1 m', left + width - 29, top + height + 18);
    context.fillText('+0.3', 3, top + 8); context.fillText('0', 19, top + height / 2); context.fillText('−0.3', 3, top + height);
  }, [frame.range_doppler]);
  return <section className="panel heatmap-panel"><div className="panel-heading compact"><div><span className="eyebrow">RADAR SIGNAL · SIMULATED</span><h2>Range-Doppler map</h2></div><Tag tone="blue">NO CAMERA</Tag></div><div className="heatmap-wrap"><span className="axis-y">VELOCITY (m/s)</span><canvas ref={canvasRef} width={560} height={285} aria-label="Simulated range-Doppler heatmap with range and velocity axes"/></div><div className="heatmap-bottom"><span>RANGE (m)</span><span>AWR1843BOOST · 77 GHz CLASS · ≈ 1–2 m</span></div></section>;
}

function RecommendationPanel({ frame }: { frame: TelemetryFrame }) {
  return <section className={`panel recommendation recommendation-${frame.recommendation.status}`}><div className="recommendation-icon">{frame.recommendation.status === 'continue' ? <CheckCircle2 size={23}/> : frame.recommendation.status === 'rest' ? <Pause size={23}/> : <Activity size={23}/>}</div><div><span className="eyebrow">RULE-BASED DEMO FEEDBACK</span><h2>{frame.recommendation.title}</h2><p>{frame.recommendation.message}</p><small>Research prototype · not medical advice or a clinical recommendation.</small></div></section>;
}

function SystemStatus({ frame }: { frame: TelemetryFrame }) {
  const entries = [
    ['AWR1843BOOST', frame.system.radar, true], ['DCA1000EVM', frame.system.capture, true],
    ['RADAR STREAM', frame.system.radar_stream, frame.running], ['AI ENGINE', frame.system.ai_engine, true],
    ['IMU GROUND TRUTH', frame.system.imu, false], ['sEMG GROUND TRUTH', frame.system.semg, false],
  ] as const;
  return <section className="panel system-panel" id="system"><div className="panel-heading compact"><div><span className="eyebrow">TRANSPARENT SYSTEM STATE</span><h2>System status</h2></div><ShieldCheck size={20} className="system-icon"/></div><div className="system-grid">{entries.map(([label, status, online]) => <div className="system-row" key={label}><span>{label}</span><strong className={online ? 'online' : 'offline'}><i/>{status}</strong></div>)}</div></section>;
}

function DeveloperPanel({ frame }: { frame: TelemetryFrame }) {
  const entries = [
    ['Frame rate', `${frame.debug.frame_rate_hz.toFixed(1)} Hz`],
    ['Radar frames received', frame.debug.radar_frames_received.toLocaleString()],
    ['Processing latency', `${frame.debug.processing_latency_ms.toFixed(3)} ms`],
    ['AI inference latency', `${frame.debug.ai_inference_latency_ms.toFixed(3)} ms`],
    ['Packet status', frame.debug.packet_status],
    ['Current rep', String(frame.movement.rep_count)],
    ['Session ID', frame.session_id],
    ['Data source', frame.data_source],
  ];
  return <div className="debug-grid">{entries.map(([label, value]) => <div key={label}><span>{label}</span><strong>{value}</strong></div>)}</div>;
}

function InformationModal({ kind, close }: { kind: 'how' | 'calibration'; close: () => void }) {
  useEffect(() => { const onEscape = (event: KeyboardEvent) => { if (event.key === 'Escape') close(); }; window.addEventListener('keydown', onEscape); return () => window.removeEventListener('keydown', onEscape); }, [close]);
  return <div className="modal-backdrop" onMouseDown={event => { if (event.target === event.currentTarget) close(); }}><div className="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title"><button className="modal-close" aria-label="Close" onClick={close}><X size={19}/></button>{kind === 'how' ? <><span className="eyebrow">TRUE REHABILITATION INTELLIGENCE</span><h2 id="modal-title">How TrueRehab-RF works</h2><ol><li>Radar observes body movement contactlessly, with no camera.</li><li>Signal processing extracts movement and micro-motion patterns.</li><li>Temporal AI is designed to compare how those patterns change across repetitions.</li><li>The intended models will estimate fatigue-related movement changes after training and validation.</li><li>Increasing predicted compensation risk can trigger a corrective cue.</li></ol><p className="modal-note">Current dashboard outputs are simulated. No trained or clinically validated model is running, and this research prototype is not intended for clinical diagnosis.</p></> : <><span className="eyebrow">FUTURE PERSONALIZATION</span><h2 id="modal-title">User calibration</h2><p>A future calibration session may use 3–5 controlled repetitions to establish a personal movement baseline before exercise monitoring.</p><p className="modal-note">Calibration is a research concept. This prototype does not calculate or store a validated personal baseline.</p></>}</div></div>;
}

function Architecture() {
  const chain = ['PERSON', 'AWR1843BOOST', 'DCA1000EVM', 'RAW ADC / I-Q', 'SIGNAL PROCESSING', 'FEATURE EXTRACTION', 'REPLACEABLE AI MODEL', 'WEBSOCKET', 'DASHBOARD'];
  return <section className="architecture-section" id="architecture"><SectionTitle eyebrow="FROM CONCEPT TO PHYSICAL PROTOTYPE" title="A replaceable hardware-to-dashboard pipeline" note="REAL RADAR INTEGRATION · FUTURE"/><div className="architecture-chain">{chain.map((step, index) => <div className="architecture-step" key={step}><span>{String(index + 1).padStart(2, '0')}</span><strong>{step}</strong>{index < chain.length - 1 && <ArrowRight size={14}/>}</div>)}</div><div className="future-grid"><div className="future-card"><FlaskConical size={20}/><div><h3>Ground-truth development</h3><p>ESP32 + LSM6DSOX IMU and MyoWare 2.0 sEMG are planned for synchronized reference data during model training. Load cell + HX711 remains optional.</p></div></div><div className="future-card"><Settings2 size={20}/><div><h3>Data collection mode · planned</h3><p>Future sessions can record radar, IMU, sEMG and condition labels together. No sensor acquisition or trained inference is claimed in this release.</p></div></div></div></section>;
}

function App() {
  const [frame, setFrame] = useState<TelemetryFrame>(() => new BrowserDemoSource().initial);
  const [sourceKind, setSourceKind] = useState<'backend' | 'browser'>('browser');
  const [busy, setBusy] = useState(false);
  const [exhibition, setExhibition] = useState(false);
  const [debugOpen, setDebugOpen] = useState(false);
  const [modal, setModal] = useState<'how' | 'calibration' | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const sourceRef = useRef<TelemetrySource | null>(null);

  useEffect(() => {
    let cancelled = false;
    let unsubscribe: (() => void) | undefined;
    createTelemetrySource().then(source => {
      if (cancelled) { source.dispose(); return; }
      sourceRef.current = source;
      setSourceKind(source.kind);
      setFrame(source.initial);
      unsubscribe = source.subscribe(setFrame);
    });
    return () => { cancelled = true; unsubscribe?.(); sourceRef.current?.dispose(); sourceRef.current = null; };
  }, []);
  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(null), 4200);
    return () => window.clearTimeout(timer);
  }, [notice]);

  const act = async (action: (source: TelemetrySource) => Promise<void>, success?: string) => {
    if (!sourceRef.current || busy) return;
    setBusy(true);
    try { await action(sourceRef.current); if (success) setNotice(success); }
    catch (error) { setNotice(error instanceof Error ? error.message : 'The action could not be completed.'); }
    finally { setBusy(false); }
  };

  const riskHigh = frame.ai.compensation_risk >= .6;
  const compensationHigh = frame.ai.compensation_level >= .4;
  const story = compensationHigh ? 'Compensatory movement has emerged in this demo.' : riskHigh ? 'Simulated risk rises before visible compensation.' : 'Movement is being monitored across repetitions.';

  return <div className={`app-shell ${exhibition ? 'exhibition' : ''}`} id="dashboard"><header className="site-header"><a href="#dashboard" className="brand"><span className="brand-mark"><Radar size={24}/></span><span><strong>TrueRehab<span>-RF</span></strong><small>CONTACTLESS AI REHABILITATION MONITORING</small></span></a><nav aria-label="Main navigation"><a href="#dashboard">Dashboard</a><a href="#timeline">Live Analysis</a><a href="#signal">Radar Signal</a><a href="#architecture">Technology</a><a href="#about">About</a></nav><div className="header-badges"><Tag tone="teal"><i className="live-dot"/> SYSTEM READY</Tag><Tag tone="amber">DEMO MODE</Tag></div></header>
    <main className="container"><div className="page-heading"><div><span className="eyebrow">77-GHz mmWAVE RADAR <b>/</b> TEMPORAL AI <b>/</b> PROTOTYPE</span><h1>Distinguishing true recovery <span>from compensation.</span></h1><p>Contactless movement monitoring across repetitions, presented as a research simulation.</p></div><div className="heading-actions"><button className="button outline" onClick={() => setModal('how')}><CircleHelp size={16}/> HOW IT WORKS</button><button className="button outline exhibition-toggle" onClick={() => setExhibition(value => !value)}><Maximize2 size={15}/>{exhibition ? 'EXIT EXHIBITION' : 'EXHIBITION MODE'}</button></div></div>
      <div className="demo-notice"><Info size={16}/><span><strong>DEMO / SIMULATION MODE.</strong> AI outputs, radar imagery and recommendations are simulated. No trained model or clinical validation is claimed.</span><span className="source-chip">SOURCE: {frame.data_source}</span></div>
      <StatusStrip frame={frame}/>
      <SessionControls frame={frame} busy={busy} onStart={() => void act(source => source.start())} onStop={() => void act(source => source.stop())} onReset={() => void act(source => source.reset(), 'Session reset')} onExport={() => void act(source => source.exportCsv(), 'CSV export started')} onSave={() => void act(async source => { setNotice(await source.saveSession()); })} onCalibration={() => setModal('calibration')}/>
      <section className="hero-grid"><div className="panel patient-panel"><div className="panel-heading"><div><span className="eyebrow">01 / RADAR OBSERVATION</span><h2>Contactless biceps curl monitoring</h2><p>One person · one radar · no camera feed</p></div><Tag tone="blue">{frame.running ? 'STREAMING' : 'DEMO PREVIEW'}</Tag></div><RadarIllustration frame={frame}/><div className="patient-footer"><span><i className="legend-dot teal"/> EXERCISE <strong>Biceps Curl / Elbow Flexion</strong></span><span><i className="legend-dot blue"/> MOVEMENT PHASE <strong>{frame.movement.phase}</strong></span></div></div><div className="hero-metrics"><div className="rep-feature"><span>REPETITION <em>· PEAK DETECTED</em></span><strong>{String(frame.movement.rep_count).padStart(2, '0')}</strong><small>CURRENT SET <b>{frame.movement.rep_count} / 10</b></small></div><div className="metric-grid"><MetricCard label="MOVEMENT QUALITY" value={frame.movement.movement_quality} suffix=" / 100" caption={`${qualityLabel(frame.movement.movement_quality)} · AI ESTIMATE`} tone="teal"/><MetricCard label="ESTIMATED MUSCLE FATIGUE" value={percent(frame.ai.fatigue_estimate)} caption={`${fatigueLabel(frame.ai.fatigue_estimate)} · AI ESTIMATE`} tone="amber"/><MetricCard label="COMPENSATION LEVEL" value={percent(frame.ai.compensation_level)} caption={`${compensationLabel(frame.ai.compensation_level)} · CURRENT`} tone={compensationHigh ? 'red' : 'orange'}/><MetricCard label="FUTURE COMPENSATION RISK" value={percent(frame.ai.compensation_risk)} caption={`${riskLabel(frame.ai.compensation_risk)} · NEXT`} tone={riskHigh ? 'red' : 'blue'} prominent/></div></div></section>
      <div className={`story-ribbon ${riskHigh ? 'attention' : ''}`}><span className="story-indicator"><Activity size={18}/></span><div><small>WHAT THE DEMO IS SHOWING</small><strong>{story}</strong></div><span className="story-detail">FATIGUE <b>{percent(frame.ai.fatigue_estimate)}</b> <ArrowRight size={13}/> RISK <b>{percent(frame.ai.compensation_risk)}</b> <ArrowRight size={13}/> CURRENT COMPENSATION <b>{percent(frame.ai.compensation_level)}</b></span></div>
      <TimelineChart frame={frame}/>
      <div className="technical-grid"><MovementSignal frame={frame}/><RangeDopplerMap frame={frame}/></div>
      <div className="bottom-grid"><RecommendationPanel frame={frame}/><SystemStatus frame={frame}/></div>
      <div className="developer-section"><button className="developer-toggle" onClick={() => setDebugOpen(value => !value)} aria-expanded={debugOpen}><Settings2 size={16}/> DEVELOPER DETAILS <span>{debugOpen ? 'HIDE' : 'SHOW'}</span></button>{debugOpen && <DeveloperPanel frame={frame}/>}</div>
      <Architecture/>
      <footer id="about"><div><strong>TrueRehab-RF</strong><span>Prasarnmit Demonstration School (Secondary), Thailand · AEII 2026 Hong Kong</span></div><p>Project team: MR. PHISIT CHAROENKITPEETI · MR. Tanakirt Jiraphongsakul · MR. Pattadon Yuttaworawit · MS. Lapattada Thaweekul</p><small>Research prototype. Not intended for clinical diagnosis.</small></footer>
    </main>{modal && <InformationModal kind={modal} close={() => setModal(null)} />}{notice && <div className="toast" role="status">{notice}</div>}
    <div className="source-accessibility" aria-hidden="true">{sourceKind === 'backend' ? 'Python backend WebSocket' : 'Browser simulation fallback'}</div>
  </div>;
}

export default App;
