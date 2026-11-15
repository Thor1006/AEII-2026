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
SOURCES = (sorted(MODEL_DIR.glob("*.py")) + sorted((MODEL_DIR / "trnet").glob("*.py"))
           + sorted((REPO / "recorder" / "rec").glob("*.py")) + [REPO / "recorder" / "checksums.py"])


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
        for p in sorted(win.glob("*.ps1")) + sorted(win.glob("*.cmd")):
            data = p.read_bytes()
            self.assertTrue(data.isascii(), f"{p.name}: Windows PowerShell 5.1 misreads non-ASCII without a BOM")
        for p in sorted(win.glob("*.cmd")):
            data = p.read_bytes()
            self.assertEqual(data.count(b"\n"), data.count(b"\r\n"), f"{p.name} needs CRLF line endings")


if __name__ == "__main__":
    unittest.main()
