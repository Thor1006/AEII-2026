"""Local-only real AWR2944P TDM point-cloud viewer. No flash or replay."""
import argparse
import json
import logging
import math
import secrets
import signal
import socket
import struct
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
import serial
from serial.tools import list_ports

MAGIC = bytes.fromhex('0201040306050807')
ROOT = Path(__file__).resolve().parent
LOG = logging.getLogger('radar')


def profile_metadata(path):
    path=Path(path)
    if not path.exists():
        return {}
    lines=[s.split() for s in path.read_text().splitlines() if s.strip() and not s.lstrip().startswith('%')]
    profile=next(s for s in lines if s[0]=='profileCfg')
    frame=next(s for s in lines if s[0]=='frameCfg')
    start,idle,adc_start,ramp,slope,samples,fs=(float(profile[i]) for i in (2,3,4,5,8,10,11))
    chirps=(int(frame[2])-int(frame[1])+1)*int(frame[3])
    period=float(frame[6])
    sample_us=samples/fs*1000
    center_hz=start*1e9+(adc_start+sample_us/2)*slope*1e6
    return dict(name=path.stem,configured_hz=1000/period,period_ms=period,
                range_resolution_cm=299792458/(2*slope*1e12*samples/(fs*1000))*100,
                doppler_resolution_m_s=299792458/(2*center_hz*chirps*(idle+ramp)*1e-6),
                acquisition_ms=chirps*(idle+ramp)/1000,
                sampled_bandwidth_ghz=slope*sample_us/1000,
                sweep_start_ghz=start,sweep_end_ghz=start+slope*ramp/1000)


def decode_packet(packet):
    if len(packet) < 40 or not packet.startswith(MAGIC):
        raise ValueError('Invalid packet header')
    version, size, platform, frame, cycles, count, ntlv, subframe = struct.unpack_from('<8I', packet, 8)
    if size != len(packet) or size > 1048576 or ntlv > 128:
        raise ValueError('Invalid packet length')
    if version != 0x04070201 or platform != 0x2944 or subframe != 0:
        raise ValueError('Packet platform/version mismatch')
    points, side, offset, stats, temperature = [], [], 40, None, None
    for _ in range(ntlv):
        if offset + 8 > size:
            raise ValueError('Truncated TLV header')
        kind, length = struct.unpack_from('<II', packet, offset)
        offset += 8
        if offset + length > size:
            raise ValueError('Truncated TLV payload')
        if kind == 1:
            if length % 16:
                raise ValueError('Invalid point payload')
            for x, y, z, v in struct.iter_unpack('<4f', packet[offset:offset+length]):
                if not all(math.isfinite(a) for a in (x, y, z, v)):
                    raise ValueError('Non-finite point')
                points.append(dict(x=x, y=y, z=z, velocity=v, range=math.sqrt(x*x+y*y+z*z)))
        elif kind == 7:
            if length % 4:
                raise ValueError('Invalid side information')
            side = list(struct.iter_unpack('<HH', packet[offset:offset+length]))
        elif kind == 6:
            if length!=24:
                raise ValueError('Invalid statistics payload')
            stats=dict(zip(('processing_us','transmit_us','margin_us','chirp_margin_us','active_cpu_percent','idle_cpu_percent'),struct.unpack_from('<6I',packet,offset)))
            stats['remaining_us']=stats['margin_us']-stats['transmit_us']
        elif kind == 9:
            if length!=28:
                raise ValueError('Invalid temperature payload')
            valid,timestamp,*sensors=struct.unpack_from('<iI10h',packet,offset)
            # On AWR2x44P the legacy DIG0 field is TX3; DIG1 is reserved.
            temperature=dict(valid=valid==0,time_ms=timestamp,max_c=max(sensors[:9]) if valid==0 else None)
        offset += length
    if len(points) != count:
        raise ValueError('Point count mismatch')
    for p, (snr, noise) in zip(points, side):
        p.update(snr_db=snr/10, noise_db=noise/10)
    return dict(frame=frame, points=points, platform=hex(platform), bytes=size,stats=stats,temperature=temperature)


def pop_packets(buffer):
    packets, invalid, skipped = [], 0, 0
    while len(buffer) >= 8:
        pos = buffer.find(MAGIC)
        if pos < 0:
            skipped += max(0, len(buffer)-7)
            del buffer[:-7]
            break
        if pos:
            skipped += pos
            del buffer[:pos]
        if len(buffer) < 40:
            break
        size = struct.unpack_from('<I', buffer, 12)[0]
        if not 40 <= size <= 1048576:
            del buffer[0]
            invalid += 1
            continue
        if len(buffer) < size:
            break
        packet = bytes(buffer[:size])
        del buffer[:size]
        try:
            packets.append(decode_packet(packet))
        except ValueError:
            invalid += 1
    return packets, invalid, skipped


def open_port(name, baud):
    port = serial.Serial()
    port.port, port.baudrate, port.timeout = name, baud, 0.02 if baud==3125000 else 0.1
    port.dtr, port.rts = False, False
    port.open()
    if baud==3125000 and hasattr(port,'set_buffer_size'):
        try:
            port.set_buffer_size(rx_size=65536,tx_size=65536)
        except serial.SerialException:
            LOG.info('Driver uses its default serial buffers')
    return port


class Radar:
    def __init__(self, profile, cli='COM5', data='COM6', max_seconds=900):
        self.profile, self.cli_name, self.data_name = Path(profile), cli, data
        self.max_seconds = max_seconds
        self.lock, self.operation = threading.RLock(), threading.Lock()
        self.ctl = self.aux = self.reader = None
        self.halt = threading.Event()
        self.mode, self.message = 'stopped', 'Ready. Start to read the real radar.'
        self.points, self.frames, self.frame = [], 0, None
        self.bad, self.gaps, self.received = 0, 0, 0
        self.started = self.last_packet = self.last_client = 0.0
        self.rate_times = []
        self.metadata=profile_metadata(self.profile)
        self.stats=self.temperature=None
        self.minimum_remaining_us=self.maximum_temperature_c=None
        self.maximum_processing_us=self.maximum_transmit_us=0
        self.stop_confirmed=True
        self.low_reserve_frames=0
        self.recent_frames=deque(maxlen=32)

    def command(self, text, timeout=6):
        self.ctl.reset_input_buffer()
        payload=(text+'\r').encode('ascii')
        if text=='sensorStop':
            # Busy demo CLI can drop a burst of input characters. Pace stop only.
            for byte in payload:
                self.ctl.write(bytes([byte]));self.ctl.flush();time.sleep(0.005)
        else:
            self.ctl.write(payload)
        self.ctl.flush()
        reply = bytearray()
        end = time.monotonic()+timeout
        while time.monotonic() < end:
            reply.extend(self.ctl.read(4096))
            if b'mmwDemo:/>' in reply:
                break
        result = reply.decode('utf-8', errors='replace')
        LOG.info('CLI %s => %s', text, result.replace('\r','').replace('\n',' | '))
        if b'mmwDemo:/>' not in reply or any(s in result for s in ('Error','not recognized','Exception')):
            raise RuntimeError('Radar rejected or did not answer: '+text)
        return result

    def start(self):
        with self.operation:
            with self.lock:
                if self.mode in ('starting','running'):
                    return
                self.mode, self.message = 'starting', 'Checking firmware and sending the tested TI profile...'
                self.points, self.frames, self.frame = [], 0, None
                self.bad, self.gaps, self.received = 0, 0, 0
                self.started = self.last_packet = 0.0
                self.rate_times = []
                self.stats=self.temperature=None
                self.minimum_remaining_us=self.maximum_temperature_c=None
                self.maximum_processing_us=self.maximum_transmit_us=0
                self.low_reserve_frames=0
                self.recent_frames.clear()
            try:
                ports = {p.device:p for p in list_ports.comports()}
                selected = [ports.get(self.cli_name), ports.get(self.data_name)]
                if not all(p and p.vid==0x0451 and p.pid==0xBEF3 for p in selected):
                    raise RuntimeError('Expected TI XDS110 ports are not connected. Check USB and power.')
                if selected[0].serial_number != selected[1].serial_number:
                    raise RuntimeError('COM ports belong to different boards.')
                self.ctl = open_port(self.cli_name,115200)
                version = self.command('version')
                if not all(t in version for t in ('AWR2X44P','TDM','04.07.02.01')):
                    raise RuntimeError('Expected AWR2X44P / TDM / SDK 04.07.02.01 firmware.')
                self.aux = open_port(self.data_name,3125000)
                self.aux.reset_input_buffer()
                self.halt.clear()
                self.reader = threading.Thread(target=self.read_loop,daemon=True)
                self.reader.start()
                for line in self.profile.read_text().splitlines():
                    line=line.strip()
                    if line and not line.startswith('%'):
                        self.command(line,25 if line=='sensorStart' else 6)
                        if line=='sensorStart':
                            self.stop_confirmed=False
                        time.sleep(0.04)
                with self.lock:
                    self.started=self.last_client=time.monotonic()
                    self.mode,self.message='running','Real TI OOB point cloud. No replay or simulated data.'
                LOG.info('RUNNING real radar')
            except Exception as error:
                self.close_ports()
                with self.lock:
                    self.mode,self.message='error',str(error)
                LOG.exception('Start failed')
                raise

    def close_ports(self):
        if self.ctl is not None and self.ctl.is_open:
            self.stop_confirmed=False
            for attempt in range(3):
                try:
                    self.command('sensorStop',4)
                    self.stop_confirmed=True
                    break
                except Exception:
                    LOG.warning('Stop attempt %s failed',attempt+1,exc_info=True)
        self.halt.set()
        if self.reader and self.reader is not threading.current_thread():
            self.reader.join(timeout=2)
        for port in (self.aux,self.ctl):
            if port is not None and port.is_open:
                port.close()
        self.ctl=self.aux=self.reader=None

    def stop(self,reason='Stopped. The last received frame remains visible.'):
        with self.operation:
            with self.lock:
                self.mode='stopping'
            self.close_ports()
            with self.lock:
                self.mode,self.message=('stopped',reason) if self.stop_confirmed else ('error','Cannot confirm radar stopped. Reset/power-off may be needed; serial ports released.')
            LOG.info('STOPPED %s',reason)

    def read_loop(self):
        buffer=bytearray()
        try:
            while not self.halt.is_set():
                chunk=self.aux.read(min(max(self.aux.in_waiting,1),65536))
                buffer.extend(chunk)
                packets,bad,skipped=pop_packets(buffer)
                now=time.monotonic()
                with self.lock:
                    self.received+=len(chunk)
                    self.bad+=bad
                    for packet in packets:
                        if self.frame is not None and (packet['frame']-self.frame)%2**32!=1:
                            self.gaps+=1
                            LOG.warning('Frame sequence discontinuity %s -> %s during %s',self.frame,packet['frame'],self.mode)
                        self.frames+=1
                        self.frame,self.points=packet['frame'],packet['points']
                        self.recent_frames.append(dict(frame=self.frame,points=self.points,received_at=now))
                        self.stats,self.temperature=packet['stats'],packet['temperature']
                        if self.stats and self.frames>2:
                            remaining=self.stats['remaining_us']
                            self.minimum_remaining_us=remaining if self.minimum_remaining_us is None else min(self.minimum_remaining_us,remaining)
                            self.maximum_processing_us=max(self.maximum_processing_us,self.stats['processing_us'])
                            self.maximum_transmit_us=max(self.maximum_transmit_us,self.stats['transmit_us'])
                            period_us=self.metadata.get('period_ms',0)*1000
                            self.low_reserve_frames=self.low_reserve_frames+1 if period_us and remaining<period_us*0.05 else 0
                            if self.low_reserve_frames>=3:
                                raise RuntimeError('Timing reserve fell below 5 percent for three frames')
                        if self.temperature and self.temperature['valid']:
                            t=self.temperature['max_c']
                            self.maximum_temperature_c=t if self.maximum_temperature_c is None else max(self.maximum_temperature_c,t)
                            if t>=85:
                                raise RuntimeError('Temperature reached conservative 85 C test limit')
                        self.last_packet=now
                        self.rate_times.append(now)
                    self.rate_times=[t for t in self.rate_times if now-t<=5]
        except Exception as error:
            if not self.halt.is_set():
                with self.lock:
                    self.mode,self.message='error','Radar data disconnected: '+str(error)
                LOG.exception('Data reader failed')
                threading.Thread(target=self.stop,args=('Acquisition stopped: '+str(error),),daemon=True).start()

    def snapshot(self,heartbeat=True,after_frame=None):
        now=time.monotonic()
        with self.lock:
            if heartbeat:
                self.last_client=now
            age=now-self.last_packet if self.last_packet else None
            rate=((len(self.rate_times)-1)/(self.rate_times[-1]-self.rate_times[0])
                  if len(self.rate_times)>1 and self.rate_times[-1]>self.rate_times[0] else 0)
            history=[]
            if after_frame is not None:
                reset=self.frame is not None and after_frame>self.frame
                history=[dict(frame=f['frame'],points=f['points'],age_seconds=now-f['received_at']) for f in self.recent_frames if reset or f['frame']>after_frame]
            return dict(service='TrueRehab local radar diagnostic',mode=self.mode,message=self.message,
                live=self.mode=='running' and age is not None and age<2,frame=self.frame,frames_received=self.frames,
                points=list(self.points),point_count=len(self.points),invalid_packets=self.bad,frame_gaps=self.gaps,
                received_bytes=self.received,age_seconds=age,rate_hz=round(rate,1),
                stop_confirmed=self.stop_confirmed,
                recent_frames=history,
                profile=self.metadata,stats=self.stats,temperature=self.temperature,
                minimum_remaining_us=self.minimum_remaining_us,maximum_temperature_c=self.maximum_temperature_c,
                maximum_processing_us=self.maximum_processing_us,maximum_transmit_us=self.maximum_transmit_us,
                runtime_seconds=round(now-self.started,1) if self.started else 0,max_seconds=self.max_seconds,
                cli_port=self.cli_name,data_port=self.data_name,
                source='LIVE HARDWARE ONLY / AWR2944PEVM / TI TDM SDK 04.07.02.01 / processed points, NOT raw ADC')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--profile',required=True)
    parser.add_argument('--port',type=int,default=8766)
    parser.add_argument('--max-seconds',type=int,default=900)
    args=parser.parse_args()
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    radar=Radar(args.profile,max_seconds=args.max_seconds)
    token,closing=secrets.token_urlsafe(32),threading.Event()
    expected_host=f'127.0.0.1:{args.port}'
    origin='http://'+expected_host

    class Handler(BaseHTTPRequestHandler):
        protocol_version='HTTP/1.1'

        def setup(self):
            super().setup()
            self.connection.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY,1)

        def log_message(self,fmt,*values):
            if not self.path.startswith('/api/state'):
                LOG.info(fmt,*values)

        def respond(self,value,code=200,kind='application/json'):
            payload=json.dumps(value).encode() if kind=='application/json' else value.encode()
            self.send_response(code)
            for key,value in {'Content-Type':kind+'; charset=utf-8','Content-Length':str(len(payload)),
                'Cache-Control':'no-store','X-Content-Type-Options':'nosniff',
                'Content-Security-Policy':"default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'"}.items():
                self.send_header(key,value)
            self.end_headers()
            self.wfile.write(payload)

        def trusted_host(self):
            return self.headers.get('Host')==expected_host

        def do_GET(self):
            if not self.trusted_host():
                return self.respond({'error':'Invalid host'},403)
            if self.path=='/':
                return self.respond((ROOT/'index.html').read_text(encoding='utf-8').replace('{{TOKEN}}',token),kind='text/html')
            if self.path=='/drive/':
                return self.respond((ROOT.parent/'radar-car-demo'/'index.html').read_text(encoding='utf-8').replace('{{TOKEN}}',token),kind='text/html')
            request=urlsplit(self.path)
            if request.path=='/api/state':
                try:
                    after=int(parse_qs(request.query).get('after',['0'])[0])
                except (ValueError,IndexError):
                    return self.respond({'error':'Invalid frame cursor'},400)
                return self.respond(radar.snapshot(after_frame=after))
            if self.path=='/api/health':
                return self.respond(radar.snapshot(False))
            return self.respond({'error':'Not found'},404)

        def do_POST(self):
            if (not self.trusted_host() or self.headers.get('Origin') not in (None,origin)
                or not secrets.compare_digest(self.headers.get('X-Radar-Token',''),token)):
                return self.respond({'error':'Local viewer authorization required'},403)
            try:
                if self.path=='/api/start':
                    radar.start()
                elif self.path=='/api/stop':
                    radar.stop()
                elif self.path=='/api/shutdown':
                    radar.stop('Viewer closed. Serial ports released.')
                    closing.set()
                else:
                    return self.respond({'error':'Not found'},404)
                self.respond(radar.snapshot())
                self.wfile.flush()
                if self.path=='/api/shutdown':
                    threading.Thread(target=httpd.shutdown,daemon=True).start()
                return
            except Exception as error:
                return self.respond({'error':str(error),'state':radar.snapshot()},500)

    httpd=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    httpd.daemon_threads=True

    def watchdog():
        while not closing.wait(1):
            with radar.lock:
                active=radar.mode=='running'
                unattended=time.monotonic()-radar.last_client>15
                expired=radar.started and time.monotonic()-radar.started>=args.max_seconds
            if active and (unattended or expired):
                radar.stop('Safety stop: viewer disconnected.' if unattended else '15-minute safety limit reached. Press Start to resume.')

    def end_signal(*_):
        closing.set()
        threading.Thread(target=httpd.shutdown,daemon=True).start()

    for signum in (signal.SIGINT,signal.SIGTERM):
        signal.signal(signum,end_signal)
    threading.Thread(target=watchdog,daemon=True).start()
    LOG.info('LOCAL VIEWER READY %s; sensor waits for Start',origin)
    try:
        httpd.serve_forever(poll_interval=0.3)
    finally:
        closing.set()
        radar.stop('Viewer server stopped.')
        httpd.server_close()


if __name__=='__main__':
    main()
