"""checksums.sha256: written when a session closes, read by macOS's shasum, and every kind of damage is named."""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

from rec import checksums  # noqa: E402
from rec import session as S  # noqa: E402

import checksums as cli  # noqa: E402


def closed_session(root):
    sess = S.SessionWriter(root, "TEST", "sums")
    (sess.dir / "radar.bin").write_bytes(bytes(range(256)) * 40)
    (sess.dir / "emg.csv").write_text("t_ns,line\n1,E,0,2048,300\n")
    sess.marker(" ")
    sess.close({"markers": 1})
    return sess


class ChecksumTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_written_at_close_and_shasum_agrees(self):
        sess = closed_session(self.tmp)
        self.assertEqual(sess.n_checksummed, 4)  # radar.bin, emg.csv, markers.csv, meta.json
        names = sorted(checksums.read(sess.dir))
        self.assertEqual(names, ["emg.csv", "markers.csv", "meta.json", "radar.bin"])
        self.assertEqual(checksums.verify(sess.dir)["status"], "ok")
        if shutil.which("shasum"):
            r = subprocess.run(["shasum", "-a", "256", "-c", checksums.NAME], cwd=sess.dir,
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_one_changed_byte_is_named(self):
        d = closed_session(self.tmp).dir
        with open(d / "radar.bin", "r+b") as f:
            f.seek(500)
            f.write(b"\x00")
        r = checksums.verify(d)
        self.assertEqual((r["status"], r["changed"], r["missing"]), ("changed", ["radar.bin"], []))

    def test_missing_and_extra_files(self):
        d = closed_session(self.tmp).dir
        (d / "emg.csv").unlink()
        (d / "notes.txt").write_text("added later")
        (d / ".DS_Store").write_bytes(b"finder")       # hidden files are ignored
        (d / "._radar.bin").write_bytes(b"exfat")
        r = checksums.verify(d)
        self.assertEqual((r["status"], r["missing"], r["extra"]), ("changed", ["emg.csv"], ["notes.txt"]))

    def test_add_never_replaces_and_verify_exit_codes(self):
        d = closed_session(self.tmp).dir
        before = (d / checksums.NAME).read_text()
        self.assertIsNone(checksums.write(d))
        old = self.tmp / "old"
        old.mkdir()
        (old / "meta.json").write_text("{}")
        self.assertEqual(cli.main(["verify", str(self.tmp)]), 0)       # "old" has no checksum: not a failure
        self.assertEqual(cli.main(["add", str(self.tmp)]), 0)
        self.assertEqual((d / checksums.NAME).read_text(), before)
        self.assertEqual(checksums.verify(old)["status"], "ok")
        (old / "meta.json").write_text('{"changed": 1}')
        self.assertEqual(cli.main(["verify", str(self.tmp)]), 1)
        self.assertEqual(cli.main(["verify", str(old)]), 1)


if __name__ == "__main__":
    unittest.main()
