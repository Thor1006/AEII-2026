/**
 * Source registry. The start screen shows the main three (Pi, demo, recording) as
 * big cards and everything else under "More options", with a form built from `fields`.
 * Adding an input means writing a SensorSource and calling `registerSource`.
 */
import { normalizePiAddress } from '../../lib/address.ts';
import type { SensorSource } from '../SensorSource.ts';
import { MockSource } from './MockSource.ts';
import { ReplaySource } from './ReplaySource.ts';
import { WebSerialSource, isWebSerialSupported } from './WebSerialSource.ts';
import { WebSocketSource } from './WebSocketSource.ts';

export type FieldValue = string | number | File | undefined;

export interface SourceField {
  name: string;
  label: string;
  type: 'text' | 'number' | 'file' | 'select';
  default?: string | number;
  options?: string[];
  placeholder?: string;
  accept?: string;
  help?: string;
}

export interface SourceDefinition {
  kind: string;
  label: string;
  description: string;
  fields: SourceField[];
  /** Return a string explaining why the source is unavailable, or true. */
  isSupported?: () => true | string;
  create(values: Record<string, FieldValue>): SensorSource;
}

export const sourceRegistry: SourceDefinition[] = [
  {
    kind: 'websocket',
    label: 'Raspberry Pi kit',
    description: 'Live data from a kit on the same Wi-Fi.',
    fields: [{ name: 'address', label: 'Pi address', type: 'text', placeholder: 'trh-kit-01.local', help: 'Printed on the kit sticker' }],
    create: (v) => {
      const url = normalizePiAddress(String(v.address ?? ''));
      if (!url) throw new Error('Type the Pi’s address, e.g. trh-kit-01.local or 192.168.1.20');
      return new WebSocketSource({ url });
    },
  },
  {
    kind: 'mock',
    label: 'Demo data',
    description: 'Made-up data, to try the dashboard without a kit.',
    fields: [{ name: 'fps', label: 'Frames per second', type: 'number', default: 20 }],
    create: (v) => new MockSource({ fps: Number(v.fps ?? 20) }),
  },
  {
    kind: 'replay',
    label: 'Recording',
    description: 'Play back a session saved with the Record button.',
    fields: [{ name: 'file', label: 'File', type: 'file', accept: '.ndjson,.jsonl,.json' }],
    create: (v) => {
      if (!(v.file instanceof File)) throw new Error('Choose a recording file first');
      return new ReplaySource({ file: v.file });
    },
  },
  {
    kind: 'serial',
    label: 'Arduino on this computer (USB)',
    description: 'sEMG / force sensor plugged into this laptop. If the Arduino is plugged into the Pi, connect to the Pi instead.',
    fields: [
      { name: 'baudRate', label: 'Baud', type: 'select', default: '115200', options: ['9600', '57600', '115200', '230400', '921600'] },
      { name: 'columns', label: 'Column names', type: 'text', default: 'emg_rms,force_n', help: 'Only for plain CSV lines like "512,20.3"' },
    ],
    isSupported: () => isWebSerialSupported() || 'Needs Chrome or Edge',
    create: (v) =>
      new WebSerialSource({
        baudRate: Number(v.baudRate ?? 115200),
        columns: String(v.columns ?? '').split(',').map((s) => s.trim()).filter(Boolean),
      }),
  },
];

/** Shown as big cards on the start screen; the rest go under "More options". */
export const primarySourceKinds = ['websocket', 'mock', 'replay'];

export function registerSource(def: SourceDefinition): void {
  const i = sourceRegistry.findIndex((d) => d.kind === def.kind);
  if (i >= 0) sourceRegistry[i] = def;
  else sourceRegistry.push(def);
}

export { MockSource, ReplaySource, WebSerialSource, WebSocketSource };
