"""Build the Raspberry Pi set: deploy/pi/dist/truerehab-pi-<version>-<date>-<commit>.tar.gz (+ .sha256).

    python3 deploy/pi/build_bundle.py                                   build
    python3 deploy/pi/build_bundle.py --copy-to /Volumes/PortableSSD/TrueRehab-Pi    and copy it there

Steps: build the dashboard (npm run build), check every Python file against Python 3.11 syntax (the Pi's oldest
supported version), collect only what the Pi needs (git-tracked sources + the built dashboard; no data, caches,
replays or local settings), write VERSION.json (commit, file hashes) and pack it with tarfile (no macOS ._ files).
"""
import argparse
import ast
import datetime
import hashlib
import io
import json
import shutil
import subprocess
import sys
import tarfile
import time
import tokenize
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
VERSION = "0.2.0"
TOP = "truerehab-pi"

# (folder, keep) : git-tracked files under folder, filtered by keep(relative path)
SOURCES = {
    "pi-bridge": lambda p: not p.endswith("config.toml"),          # never a local config (it may hold a key)
    "model": lambda p: p.startswith(("model/trnet/", "model/tests/", "model/calib/")) or p in {
        "model/README.md", "model/.gitignore", "model/check_session.py", "model/export_dashboard.py",
        "model/demo.py", "model/demo_page.html", "model/train.py"},
    "radar-lab": lambda p: p.startswith(("radar-lab/radarlab/", "radar-lab/configs/", "radar-lab/tests/")) or p in {
        "radar-lab/view.py", "radar-lab/README.md"},
    "recorder": lambda p: not p.startswith("recorder/models/"),
    "firmware": lambda p: p.startswith("firmware/myoware_record/"),   # the MyoWare's sketch (git never has wifi_secrets.h)
}
ROOT_FILES = ["install.sh", "selftest.py", "config.pi.toml", "requirements-pi.txt", "requirements-model.txt",
              "truerehab-bridge.service.in", "README.md"]
EXECUTABLE = {"install.sh", "selftest.py"}
SKIP_PARTS = {"__pycache__", ".venv", "node_modules", "data", "runs", ".DS_Store"}


def git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=True).stdout


def py311_problems(src, name):
    """Syntax newer than Python 3.11: what ast's feature_version catches, plus f-strings that reuse their own quote
    character, or hold a backslash or a comment inside {...} (PEP 701, 3.12+), which ast doesn't catch."""
    out = []
    try:
        ast.parse(src, filename=name, feature_version=(3, 11))
    except SyntaxError as e:
        return [f"{name}:{e.lineno}: {e.msg}"]
    if not hasattr(tokenize, "FSTRING_START"):
        return out
    stack = []                       # (quote, depth of {} inside it)
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type == tokenize.FSTRING_START:
            quote = tok.string.lstrip("fFrRbBuU")
            if stack and stack[-1][1] > 0 and (quote == stack[-1][0] or (len(stack[-1][0]) == 1 and quote[0] == stack[-1][0])):
                out.append(f"{name}:{tok.start[0]}: f-string inside an f-string with the same quote (needs Python 3.12)")
            stack.append([quote, 0])
        elif tok.type == tokenize.FSTRING_END and stack:
            stack.pop()
        elif stack and tok.type == tokenize.OP and tok.string in "{}":
            stack[-1][1] += 1 if tok.string == "{" else -1
        elif stack and stack[-1][1] > 0:
            outer = stack[-1][0]
            if tok.type == tokenize.STRING:
                q = tok.string.lstrip("fFrRbBuU")
                if q.startswith(outer) or (len(outer) == 1 and q[0] == outer):
                    out.append(f"{name}:{tok.start[0]}: string with the f-string's own quote inside {{...}} (needs Python 3.12)")
                if "\\" in tok.string:
                    out.append(f"{name}:{tok.start[0]}: backslash inside an f-string's {{...}} (needs Python 3.12)")
            elif tok.type == tokenize.COMMENT:
                out.append(f"{name}:{tok.start[0]}: comment inside an f-string's {{...}} (needs Python 3.12)")
    return out


def collect():
    files = {}                                       # path in the set -> source path
    tracked = git("ls-files").splitlines()
    for folder, keep in SOURCES.items():
        for rel in tracked:
            if rel.startswith(folder + "/") and keep(rel) and not (set(Path(rel).parts) & SKIP_PARTS):
                if (ROOT / rel).is_file():
                    files[rel] = ROOT / rel
    dist = ROOT / "frontend" / "dist"
    for p in sorted(dist.rglob("*")):
        if p.is_file() and not (set(p.relative_to(ROOT).parts) & SKIP_PARTS) and "replays" not in p.parts:
            files[str(p.relative_to(ROOT))] = p
    for name in ROOT_FILES:
        files[name] = HERE / name
    return files


def build_frontend():
    print("building the dashboard (npm run build)...")
    p = subprocess.run(["npm", "run", "-s", "build"], cwd=ROOT / "frontend", capture_output=True, text=True)
    if p.returncode:
        sys.exit("dashboard build failed:\n" + p.stdout[-2000:] + p.stderr[-2000:])
    if not (ROOT / "frontend" / "dist" / "index.html").exists():
        sys.exit("dashboard build made no index.html")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=str(HERE / "dist"))
    ap.add_argument("--copy-to", help="also copy the set (and its .sha256) into this folder, e.g. on a drive")
    ap.add_argument("--skip-frontend-build", action="store_true", help="use the existing frontend/dist")
    a = ap.parse_args(argv)

    if not a.skip_frontend_build:
        build_frontend()
    files = collect()
    problems = []
    for rel, src in sorted(files.items()):
        if rel.endswith(".py"):
            problems += py311_problems(src.read_text(), rel)
    if problems:
        sys.exit("Python 3.11 problems (the Pi may run 3.11):\n  " + "\n  ".join(problems))
    print(f"python 3.11 syntax: ok ({sum(r.endswith('.py') for r in files)} files)")

    commit = git("rev-parse", "--short", "HEAD").strip()
    dirty = bool(git("status", "--porcelain", "--", *SOURCES, "frontend/src", "deploy/pi").strip())
    now = datetime.datetime.now().astimezone()
    version = {"name": TOP, "version": VERSION, "built": now.isoformat(timespec="seconds"), "git_commit": commit,
               "git_dirty": dirty, "python_min": "3.11", "target": "Raspberry Pi 5, Raspberry Pi OS (64-bit)",
               "files": {rel: hashlib.sha256(src.read_bytes()).hexdigest() for rel, src in sorted(files.items())}}
    out_dir = Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    name = f"{TOP}-{VERSION}-{now:%Y%m%d}-{commit}{'-modified' if dirty else ''}.tar.gz"
    out = out_dir / name
    mtime = time.time()

    def add(tar, arcname, data, mode):
        info = tarfile.TarInfo(f"{TOP}/{arcname}")
        info.size, info.mtime, info.mode = len(data), mtime, mode
        info.uid = info.gid = 0
        info.uname = info.gname = "root"
        tar.addfile(info, io.BytesIO(data))

    with tarfile.open(out, "w:gz", compresslevel=6) as tar:
        add(tar, "VERSION.json", (json.dumps(version, indent=1) + "\n").encode(), 0o644)
        for rel, src in sorted(files.items()):
            add(tar, rel, src.read_bytes(), 0o755 if rel in EXECUTABLE else 0o644)
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    (out_dir / (name + ".sha256")).write_text(f"{digest}  {name}\n")
    size_mb = out.stat().st_size / 1e6
    print(f"built {out} ({size_mb:.1f} MB, {len(files) + 1} files, commit {commit}{', MODIFIED working tree' if dirty else ''})")
    print(f"sha256 {digest}")
    if a.copy_to:
        dest = Path(a.copy_to)
        dest.mkdir(parents=True, exist_ok=True)
        for f in (out, out_dir / (name + ".sha256")):
            shutil.copyfile(f, dest / f.name)              # data only
            if sys.platform == "darwin":                   # macOS still tags new files; on exFAT that becomes ._ files
                subprocess.run(["xattr", "-c", str(dest / f.name)], check=False)
                (dest / ("._" + f.name)).unlink(missing_ok=True)
        copied = hashlib.sha256((dest / name).read_bytes()).hexdigest()
        if copied != digest:
            sys.exit(f"copy to {dest} is corrupt (sha256 differs)")
        print(f"copied to {dest} (sha256 verified)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
