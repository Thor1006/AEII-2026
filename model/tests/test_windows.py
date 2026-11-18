"""Training on the Windows PC: an NVIDIA GPU is used when there is one; every text file is read and written as UTF-8
(Windows' default code page can't write the reports' ≈ and ±); the PowerShell/cmd scripts stay plain ASCII."""
import ast
import unittest
from pathlib import Path
from unittest import mock

import torch

from _util import MODEL_DIR
from trnet import training as TRN

REPO = MODEL_DIR.parent


def files(folder, pattern):
    """Sorted matches, without hidden files: macOS leaves ._<name> helper files on the exFAT SSD (and in a copy of
    a folder taken from it), and pathlib's * matches them."""
    return sorted(p for p in Path(folder).glob(pattern) if not p.name.startswith("."))


SOURCES = (files(MODEL_DIR, "*.py") + files(MODEL_DIR / "trnet", "*.py")
           + files(REPO / "recorder" / "rec", "*.py") + [REPO / "recorder" / "checksums.py"])


def text_io_without_encoding(path):
    """(line, call) for every read_text/write_text/open in text mode that doesn't name an encoding."""
    bad = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.Call) or any(k.arg == "encoding" for k in node.keywords):
            continue
        f = node.func
        if isinstance(f, ast.Attribute) and f.attr in ("read_text", "write_text"):
            bad.append((node.lineno, f.attr))
        elif isinstance(f, ast.Name) and f.id == "open":
            mode = node.args[1] if len(node.args) > 1 else next((k.value for k in node.keywords if k.arg == "mode"), None)
            if not (isinstance(mode, ast.Constant) and "b" in str(mode.value)):
                bad.append((node.lineno, "open"))
    return bad


class WindowsTest(unittest.TestCase):
    def test_device_prefers_nvidia_then_apple_then_cpu(self):
        with mock.patch.object(torch.cuda, "is_available", return_value=True):
            self.assertEqual(TRN.pick_device("auto").type, "cuda")
        with mock.patch.object(torch.cuda, "is_available", return_value=False), \
                mock.patch.object(torch.backends.mps, "is_available", return_value=True):
            self.assertEqual(TRN.pick_device("auto").type, "mps")
        with mock.patch.object(torch.cuda, "is_available", return_value=False), \
                mock.patch.object(torch.backends.mps, "is_available", return_value=False):
            self.assertEqual(TRN.pick_device("auto").type, "cpu")
        self.assertEqual(TRN.pick_device("cpu").type, "cpu")

    def test_every_text_file_is_utf8(self):
        found = {p.relative_to(REPO).as_posix(): b for p in SOURCES if (b := text_io_without_encoding(p))}
        self.assertEqual(found, {}, "add encoding=\"utf-8\" (Windows would use its old code page)")

    def test_scripts_are_plain_ascii_and_cmd_has_windows_line_endings(self):
        win = MODEL_DIR / "windows"
        for p in files(win, "*.ps1") + files(win, "*.cmd"):
            data = p.read_bytes()
            self.assertTrue(data.isascii(), f"{p.name}: Windows PowerShell 5.1 misreads non-ASCII without a BOM")
        for p in files(win, "*.cmd"):
            data = p.read_bytes()
            self.assertEqual(data.count(b"\n"), data.count(b"\r\n"), f"{p.name} needs CRLF line endings")

    def test_macos_helper_files_are_skipped(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            for name in ("setup.ps1", "._setup.ps1", ".hidden.ps1"):
                (Path(d) / name).write_bytes(b"\x00\x05\x16\x07\xff")  # an AppleDouble header is not ASCII
            self.assertEqual([p.name for p in files(d, "*.ps1")], ["setup.ps1"])


if __name__ == "__main__":
    unittest.main()
