"""Bounded, explicitly approved runtime profile tests. Never flashes firmware."""
import argparse
import json
import logging
import time
from pathlib import Path
from server import Radar, profile_metadata


def prepare(source, folder):
    folder.mkdir(parents=True,exist_ok=True)
    baseline=Path(source).read_text()
    for hz in (10,20,30,40):
        lines=[]
        for line in baseline.splitlines():
            if line.startswith('frameCfg '):
                fields=line.split();fields[6]=f'{1000/hz:.6f}';line=' '.join(fields)
            lines.append(line)
        (folder/f'tdm-baseline-{hz}hz.cfg').write_text('\n'.join(lines)+'\n')
    wide=baseline.replace('profileCfg 0 77 186 7 57.14 0 0 70 1 656 13349 0 0 158',
                          'profileCfg 0 76.55 186 7 63.14 0 0 70 1 736 13349 0 0 158')
    if wide==baseline:
        raise RuntimeError('Source profile differs from the reviewed official baseline')
    for hz in (20,30,40):
        lines=[]
        for line in wide.splitlines():
            if line.startswith('frameCfg '):
                fields=line.split();fields[5]='736';fields[6]=f'{1000/hz:.6f}';line=' '.join(fields)
            lines.append(line)
        path=folder/f'tdm-wide-{hz}hz.cfg';path.write_text('\n'.join(lines)+'\n')
        meta=profile_metadata(path)
        if not (76.5<meta['sweep_start_ghz']<meta['sweep_end_ghz']<81):
            raise RuntimeError('Candidate outside selected VCO2 sub-band')
    print(json.dumps([profile_metadata(p) for p in sorted(folder.glob('*.cfg'))],indent=2))


def run(profile,seconds,output):
    if not 5<=seconds<=60:
        raise ValueError('Tests must be bounded to 5–60 seconds')
    radar=Radar(profile,max_seconds=int(seconds)+30)
    samples=[];last_frame=None;failure=None
    try:
        radar.start();end=time.monotonic()+seconds
        while time.monotonic()<end:
            state=radar.snapshot()
            if state['mode']!='running':
                raise RuntimeError(state['message'])
            if state['age_seconds'] is not None and state['age_seconds']>1:
                raise RuntimeError('Data became stale')
            if state['frame']!=last_frame and state['frame'] is not None:
                samples.append({k:state[k] for k in ('frame','point_count','stats','temperature','age_seconds')})
                last_frame=state['frame']
            if state['invalid_packets'] or state['frame_gaps']:
                raise RuntimeError('Malformed packet or frame sequence gap')
            if state['frames_received']>5 and state['minimum_remaining_us'] is not None:
                if state['minimum_remaining_us']<state['profile']['period_ms']*1000*0.10:
                    raise RuntimeError('Less than 10 percent measured timing headroom; lower rate needed')
            time.sleep(0.003)
    except Exception as error:
        failure=str(error)
    finally:
        radar.stop('Bounded benchmark completed; serial ports released.')
    state=radar.snapshot(False)
    if not state['stop_confirmed']:
        failure=failure or 'Sensor stop could not be confirmed'
    summary={k:state[k] for k in ('profile','frame','frames_received','rate_hz','invalid_packets','frame_gaps','received_bytes',
                                  'minimum_remaining_us','maximum_processing_us','maximum_transmit_us','maximum_temperature_c')}
    summary.update(seconds=seconds,failure=failure,sampled_unique_frames=len(samples),samples=samples)
    if state['frames_received']==0 or not samples:
        summary['failure']=failure or 'No real frames'
    path=Path(output);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(summary,indent=2))
    print('RESULT '+json.dumps({k:v for k,v in summary.items() if k!='samples'}),flush=True)
    return summary['failure'] is None


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--prepare-source');parser.add_argument('--profiles');
    parser.add_argument('--profile');parser.add_argument('--seconds',type=float,default=12);parser.add_argument('--output')
    args=parser.parse_args();logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    if args.prepare_source:
        prepare(args.prepare_source,Path(args.profiles))
    else:
        raise SystemExit(0 if run(args.profile,args.seconds,args.output) else 1)
