"""Add or verify the checksums of session folders (checksums.sha256, written by the recorder at Stop).

  python checksums.py verify <session folder or folder of sessions>
  python checksums.py add    <session folder or folder of sessions>

`add` writes a checksum file only where none exists (it never replaces one); the hashes then describe the files as
they are now, not as they were recorded. `verify` exits 1 if any file changed or went missing.
Inside one folder macOS can check it without Python: shasum -a 256 -c checksums.sha256
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rec import checksums  # noqa: E402


def sessions(path):
    """The session folders at path: path itself if it has a meta.json, else its subfolders that do."""
    path = Path(path)
    if (path / "meta.json").exists():
        return [path]
    return sorted(p for p in path.iterdir() if p.is_dir() and (p / "meta.json").exists())


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["add", "verify"])
    ap.add_argument("path")
    a = ap.parse_args(argv)
    found = sessions(a.path)
    if not found:
        print(f"no session folders (with a meta.json) in {a.path}")
        return 2
    bad = 0
    for s in found:
        if a.action == "add":
            n = checksums.write(s)
            print(f"{s.name}: " + ("already has checksums, left as it is" if n is None else f"added ({n} files)"))
            continue
        r = checksums.verify(s)
        if r["status"] == "ok":
            line = f"ok ({r['files']} files)"
        elif r["status"] == "no checksum":
            line = "no checksum (run: checksums.py add)"
        else:
            bad += 1
            parts = [f"changed: {', '.join(r['changed'])}"] if r["changed"] else []
            parts += [f"missing: {', '.join(r['missing'])}"] if r["missing"] else []
            line = "CHANGED - " + "; ".join(parts)
        if r["extra"]:
            line += f" (added since: {', '.join(r['extra'])})"
        print(f"{s.name}: {line}")
    if a.action == "verify":
        print(f"{len(found)} sessions, {bad} with a changed or missing file")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
