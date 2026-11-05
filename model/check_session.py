"""Check recorder sessions: run straight after every recording.

  python check_session.py ../recorder/data/sessions/<session>     one session
  python check_session.py --all                                    every session in recorder/data/sessions

Prints what is fine, what to look at and what can't be used, and which models the session can train.
Saves the same report as JSON in model/runs/checks/. Never changes the session folder.
Exit code 0 = usable for training, 1 = not usable (or some session isn't, with --all).
"""
import argparse
import json
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
warnings.filterwarnings("ignore", category=RuntimeWarning)

from trnet import paths  # noqa: E402
from trnet.check import check_session, format_report  # noqa: E402


def _json_safe(o):
    if isinstance(o, dict):
        return {k: _json_safe(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_json_safe(v) for v in o]
    if hasattr(o, "item"):
        return o.item()
    return o


def main(argv=None):
    ap = argparse.ArgumentParser(description="Check recorder sessions for training.")
    ap.add_argument("sessions", nargs="*", help="session folder(s)")
    ap.add_argument("--all", action="store_true", help="every session in --root")
    ap.add_argument("--root", default=str(paths.SESSIONS), help="where --all looks (default: recorder/data/sessions)")
    ap.add_argument("--no-save", action="store_true", help="don't write model/runs/checks/<session>.json")
    a = ap.parse_args(argv)
    folders = [Path(p) for p in a.sessions]
    if a.all:
        folders += sorted(p for p in Path(a.root).iterdir() if (p / "meta.json").exists())
    if not folders:
        ap.error("give a session folder or --all")
    out_dir = paths.RUNS / "checks"
    all_ok = True
    for f in folders:
        r = check_session(f)
        print(format_report(r) + "\n")
        all_ok &= r["usable"]
        if not a.no_save:
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / f"{r['session']}.json").write_text(json.dumps(_json_safe(r), indent=1))
    if len(folders) > 1:
        print(f"{sum(1 for _ in folders)} sessions checked; reports in {out_dir}" if not a.no_save else "")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
