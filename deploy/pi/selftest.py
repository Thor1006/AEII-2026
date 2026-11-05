"""TrueRehab-RF Pi set self-test. Run it with the set's own Python after install.sh:

    .venv/bin/python selftest.py              everything below
    .venv/bin/python selftest.py --quick      skip the unit tests

Checks the Python version, the packages, the settings, the unit tests that need no hardware, the radar's USB ports,
free space for recordings, and (if the bridge is running) the bridge checker against it.
Exit code 0 = no failures (warnings are fine).
"""
import argparse
import importlib
import os
import platform
import shutil
import socket
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for sub in ("pi-bridge", "model", "radar-lab", "recorder"):
    sys.path.insert(0, str(HERE / sub))

RESULTS = []


def report(level, what, detail=""):
    RESULTS.append(level)
    mark = {"ok": "✓", "warn": "!", "fail": "✗", "info": "·"}[level]
    print(f"  {mark} {what}" + (f": {detail}" if detail else ""))


def check_python():
    v = sys.version_info
    report("ok" if v >= (3, 11) else "fail", "Python", f"{v.major}.{v.minor}.{v.micro} ({sys.executable})")
    model = Path("/proc/device-tree/model")
    board = model.read_text(errors="ignore").strip("\x00\n") if model.exists() else platform.platform()
    report("info", "computer", f"{board}, {platform.machine()}")


def check_packages():
    for name, why in (("websockets", "the bridge"), ("numpy", "radar maps"), ("serial", "the radar's USB ports")):
        try:
            mod = importlib.import_module(name)
            report("ok", f"package {name}", getattr(mod, "__version__", getattr(mod, "VERSION", "")))
        except ImportError:
            report("fail", f"package {name}", f"missing ({why}); run: bash install.sh")
    try:
        import torch
        report("ok", "package torch (model tools)", torch.__version__)
    except ImportError:
        report("warn", "package torch (model tools)", "not installed: session check and replays need bash install.sh --with-model")
    for mod in ("truerehab_bridge", "truerehab_bridge.providers.radar", "trnet.radar", "radarlab.tlv", "rec.session"):
        try:
            importlib.import_module(mod)
            report("ok", f"code {mod}")
        except Exception as exc:  # noqa: BLE001
            report("fail", f"code {mod}", f"{type(exc).__name__}: {exc}")


def check_config():
    from truerehab_bridge.config import load_config
    from truerehab_bridge.server import build_providers
    path = HERE / "pi-bridge" / "config.toml"
    if not path.exists():
        path = HERE / "config.pi.toml"
        report("warn", "settings", "pi-bridge/config.toml missing (install.sh makes it); testing config.pi.toml")
    try:
        cfg = load_config(path)
        provs = build_providers(cfg)
        names = ", ".join(p.name + (" (DEMO)" if p.synthetic else "") for p in provs)
        report("ok", "settings", f"{path.name}: providers {names}; dashboard port {cfg.http_port}, key {'ON' if cfg.resolved_key() else 'off'}")
        if not (cfg.web_root / "index.html").exists():
            report("fail", "dashboard files", f"{cfg.web_root} has no index.html")
        else:
            report("ok", "dashboard files", str(cfg.web_root))
        return cfg, provs
    except Exception as exc:  # noqa: BLE001
        report("fail", "settings", f"{type(exc).__name__}: {exc}")
        return None, []


def run_tests():
    suites = [("pi-bridge", ["-m", "unittest", "discover", "tests"]),
              ("recorder", ["-m", "unittest", "discover", "-s", "tests"]),
              ("radar-lab", ["-m", "unittest", "discover", "-s", "tests"]),
              ("model", ["-m", "unittest", "discover", "-s", "tests", "-p", "test_radar.py"])]
    for folder, args in suites:
        p = subprocess.run([sys.executable, *args], cwd=HERE / folder, capture_output=True, text=True)
        tail = [ln for ln in p.stderr.splitlines() if ln.startswith(("Ran ", "OK", "FAILED"))]
        report("ok" if p.returncode == 0 else "fail", f"unit tests {folder}", " ".join(tail) or p.stderr[-300:])
        if p.returncode:
            print("\n".join("      " + ln for ln in p.stderr.splitlines()[-25:]))


def check_radar_ports():
    try:
        from serial.tools import list_ports
    except ImportError:
        return
    from truerehab_bridge.providers.radar import find_xds110_ports
    cli, data = find_xds110_ports(list_ports.comports())
    if cli and data:
        report("ok", "radar USB ports", f"commands {cli}, data {data}")
    else:
        report("warn", "radar USB ports", "not found: power the radar first, then plug in its USB cable")
    if platform.system() == "Linux":
        groups = subprocess.run(["id", "-nG"], capture_output=True, text=True).stdout.split()
        report("ok" if "dialout" in groups else "warn", "serial permission",
               "in dialout" if "dialout" in groups else "not in dialout yet (log out and in, or reboot, after install.sh)")


def check_space(cfg):
    target = Path("~/truerehab-sessions").expanduser()
    probe = target if target.exists() else target.parent
    free_gb = shutil.disk_usage(probe).free / 1e9
    report("ok" if free_gb > 2 else "warn", "space for recordings", f"{free_gb:.1f} GB free ({probe}); 1 minute of radar ~ 15 MB")
    temp = Path("/sys/class/thermal/thermal_zone0/temp")
    if temp.exists():
        c = int(temp.read_text()) / 1000
        report("ok" if c < 75 else "warn", "Pi temperature", f"{c:.0f} °C")


def check_running_bridge(cfg):
    port = cfg.ws_port if cfg else 8765
    with socket.socket() as s:
        s.settimeout(1)
        up = s.connect_ex(("127.0.0.1", port)) == 0
    if not up:
        report("warn", "running bridge", f"nothing on port {port} (sudo systemctl status truerehab-bridge)")
        return
    args = [sys.executable, str(HERE / "pi-bridge" / "check_bridge.py"), f"ws://127.0.0.1:{port}", "--seconds", "6"]
    key = cfg.resolved_key() if cfg else None
    if key:
        args += ["--key", key]
    p = subprocess.run(args, capture_output=True, text=True)
    lines = [ln for ln in p.stdout.splitlines() if ln.strip()]
    report("ok" if p.returncode == 0 else "fail", "bridge checker", lines[-1] if lines else f"exit {p.returncode}")
    if p.returncode:
        print("\n".join("      " + ln for ln in lines[-20:]))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--quick", action="store_true", help="skip the unit tests")
    a = ap.parse_args()
    version = (HERE / "VERSION.json").read_text() if (HERE / "VERSION.json").exists() else "{}"
    import json
    v = json.loads(version)
    print(f"TrueRehab-RF Pi set {v.get('version', '?')} ({v.get('git_commit', '?')}{', modified' if v.get('git_dirty') else ''}), built {v.get('built', '?')}")
    check_python()
    check_packages()
    cfg, _ = check_config()
    if not a.quick:
        run_tests()
    check_radar_ports()
    check_space(cfg)
    check_running_bridge(cfg)
    fails, warns = RESULTS.count("fail"), RESULTS.count("warn")
    print(f"\n{'PASS' if not fails else 'FAIL'}: {fails} failed, {warns} warnings")
    return 1 if fails else 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    sys.exit(main())
