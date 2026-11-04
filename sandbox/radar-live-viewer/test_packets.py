"""Synthetic fixtures are unit-test-only and are never served to the viewer."""
import argparse
import math
import struct
import unittest
import time
import tempfile
from unittest.mock import Mock
from pathlib import Path
from server import MAGIC, Radar, decode_packet, pop_packets, profile_metadata

def fixture(frame=1):
    payload=struct.pack('<4f',1,2,.5,-.25)
    body=struct.pack('<II',1,len(payload))+payload+struct.pack('<IIHH',7,4,120,30)
    return MAGIC+struct.pack('<8I',0x04070201,40+len(body),0x2944,frame,0,1,2,0)+body

class PacketTests(unittest.TestCase):
    def test_points_and_units(self):
        p=decode_packet(fixture())
        self.assertEqual(p['frame'],1)
        self.assertEqual(p['points'][0]['snr_db'],12)
        self.assertAlmostEqual(p['points'][0]['range'],math.sqrt(5.25))
    def test_partial(self):
        b=bytearray(fixture()[:31])
        self.assertEqual(pop_packets(b)[0],[])
        b.extend(fixture()[31:])
        self.assertEqual(len(pop_packets(b)[0]),1)
        self.assertEqual(len(b),0)
    def test_garbage_and_continuity(self):
        packets,bad,skipped=pop_packets(bytearray(b'garbage'+fixture(10)+fixture(11)))
        self.assertEqual([p['frame'] for p in packets],[10,11])
        self.assertEqual((bad,skipped),(0,7))
    def test_wrong_platform(self):
        b=bytearray(fixture());struct.pack_into('<I',b,16,0x6843)
        self.assertRaises(ValueError,decode_packet,bytes(b))
    def test_wrong_count(self):
        b=bytearray(fixture());struct.pack_into('<I',b,28,2)
        self.assertRaises(ValueError,decode_packet,bytes(b))
    def test_not_live_without_data(self):
        r=Radar('not-opened.cfg')
        self.assertFalse(r.snapshot(False)['live'])
        self.assertEqual(r.snapshot(False)['points'],[])
    def test_stale_data_is_never_live(self):
        r=Radar('not-opened.cfg');r.mode='running';r.last_packet=time.monotonic()-3
        self.assertFalse(r.snapshot(False)['live'])
        self.assertGreater(r.snapshot(False)['age_seconds'],2)
    def test_zero_points_is_valid(self):
        b=MAGIC+struct.pack('<8I',0x04070201,40,0x2944,2,0,0,0,0)
        self.assertEqual(decode_packet(b)['points'],[])
    def test_bad_packet_length(self):
        b=bytearray(fixture());struct.pack_into('<I',b,12,10)
        self.assertGreater(pop_packets(b)[1],0)
    def add_tlv(self,kind,payload):
        b=bytearray(fixture());b.extend(struct.pack('<II',kind,len(payload))+payload)
        struct.pack_into('<I',b,12,len(b));struct.pack_into('<I',b,32,3)
        return bytes(b)
    def test_statistics_transport_is_subtracted(self):
        p=decode_packet(self.add_tlv(6,struct.pack('<6I',1800,4300,7500,0,0,0)))
        self.assertEqual(p['stats']['processing_us'],1800)
        self.assertEqual(p['stats']['remaining_us'],3200)
    def test_temperature_reserved_sensor_is_excluded(self):
        p=decode_packet(self.add_tlv(9,struct.pack('<iI10h',0,123,*range(40,49),32767)))
        self.assertTrue(p['temperature']['valid']);self.assertEqual(p['temperature']['max_c'],48)
    def test_invalid_temperature_not_used(self):
        p=decode_packet(self.add_tlv(9,struct.pack('<iI10h',-1,123,*range(10))))
        self.assertIsNone(p['temperature']['max_c'])
    def test_truncated_statistics_rejected(self):
        self.assertRaises(ValueError,decode_packet,self.add_tlv(6,b'1234'))
    def test_profile_metadata_uses_frame_period_not_sample_count(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'example.cfg'
            p.write_text('profileCfg 0 77 186 7 57.14 0 0 70 1 656 13349 0 0 158\nframeCfg 0 3 16 0 656 25 1 0\n')
            meta=profile_metadata(p)
            self.assertEqual(meta['configured_hz'],40)
            self.assertAlmostEqual(meta['range_resolution_cm'],4.3575,places=4)
            self.assertAlmostEqual(meta['acquisition_ms'],15.56096,places=5)
    def test_stop_retries_and_requires_acknowledgement(self):
        r=Radar('not-opened.cfg');r.ctl=Mock(is_open=True)
        r.command=Mock(side_effect=[RuntimeError('truncated CLI input'),'Done'])
        with self.assertLogs('radar',level='WARNING'):
            r.close_ports()
        self.assertTrue(r.stop_confirmed);self.assertEqual(r.command.call_count,2)
    def test_unconfirmed_stop_is_an_error(self):
        r=Radar('not-opened.cfg');r.ctl=Mock(is_open=True)
        r.command=Mock(side_effect=RuntimeError('No reply'))
        with self.assertLogs('radar',level='WARNING'):
            r.stop()
        self.assertFalse(r.stop_confirmed);self.assertEqual(r.snapshot(False)['mode'],'error')
    def test_frame_history_cursor_and_session_restart(self):
        r=Radar('not-opened.cfg');r.frame=3
        for number in (1,2,3):
            r.recent_frames.append(dict(frame=number,points=[],received_at=time.monotonic()))
        self.assertEqual([p['frame'] for p in r.snapshot(False,after_frame=1)['recent_frames']],[2,3])
        self.assertEqual([p['frame'] for p in r.snapshot(False,after_frame=100)['recent_frames']],[1,2,3])
        self.assertEqual(r.snapshot(False)['recent_frames'],[])

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--capture');args=parser.parse_args()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(PacketTests))
    if not result.wasSuccessful():raise SystemExit(1)
    if args.capture:
        packets,bad,skipped=pop_packets(bytearray(Path(args.capture).read_bytes()))
        assert len(packets)==151 and bad==0 and skipped==0
        assert [p['frame'] for p in packets]==list(range(1,152))
        print('REAL CAPTURE CHECK: 151/151 packets passed; no errors or skipped bytes.')
