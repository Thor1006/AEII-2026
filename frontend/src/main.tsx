import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App.tsx';
import { initialSource } from './dashboard.config.ts';
import { sourceRegistry } from './sensor/sources/index.ts';
import { SensorProvider } from './state/SensorContext.tsx';
import '@fontsource/inter/latin-400.css';
import '@fontsource/inter/latin-500.css';
import '@fontsource/noto-sans-thai/thai-400.css';
import '@fontsource/noto-sans-thai/thai-500.css';
import './styles/global.css';

const start = initialSource;
const startDef = start ? sourceRegistry.find((d) => d.kind === start.kind) : undefined;

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <SensorProvider initialSource={start && startDef ? () => startDef.create(start.values) : undefined}>
      <App />
    </SensorProvider>
  </StrictMode>,
);
