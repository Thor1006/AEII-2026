"""TrueRehab-RF Pi set self-test. Run it with the set's own Python after install.sh:

    .venv/bin/python selftest.py              everything below
    .venv/bin/python selftest.py --quick      skip the unit tests

Checks the Python version, the packages, the settings, the unit tests that need no hardware, the radar's USB ports,
the MyoWare (sEMG) link, free space for recordings, and (if the bridge is running) the bridge checker against it.
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
import time
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
    for mod in ("truerehab_bridge", "truerehab_bridge.providers.radar", "truerehab_bridge.providers.emg", "trnet.radar",
                "radarlab.tlv", "rec.session"):
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


def bridge_running(cfg):
    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", cfg.ws_port if cfg else 8765)) == 0


def check_myoware(cfg, bridge_up):
    """The MyoWare serves one connection at a time: with the bridge running, ask the bridge (its checker reports the
    'emg' device) instead of taking the board away from it mid-recording."""
    emg = (cfg.providers.get("emg") or {}) if cfg else {}
    if not emg.get("enabled"):
        report("info", "MyoWare (sEMG)", "off in the settings: turn on [providers.emg] once the board runs firmware/myoware_record")
        return
    port = str(emg.get("port", "tcp://truerehab-myoware.local:3334"))
    if bridge_up:
        report("info", "MyoWare (sEMG)", f"{port}: checked through the running bridge below (it holds the board's one link)")
        return
    from truerehab_bridge.providers.emg import tcp_address
    tcp = tcp_address(port)
    if not tcp:
        report("ok" if Path(port).exists() else "warn", "MyoWare (sEMG) USB port",
               port + ("" if Path(port).exists() else ": not plugged in (bench only: never worn on USB)"))
        return
    try:
        with socket.create_connection(tcp, timeout=3) as s:
            s.settimeout(1.5)
            data = b""
            end = time.monotonic() + 1.0
            while time.monotonic() < end:
                chunk = s.recv(65536)
                if not chunk:
                    break
                data += chunk
        n = data.count(b"\nE,")
        report("ok" if n > 500 else "warn", "MyoWare (sEMG)", f"{port}: {n} samples in 1 s" + ("" if n > 500 else " (expected ~1000)"))
    except OSError as exc:
        report("warn", "MyoWare (sEMG)", f"{port}: not reachable ({type(exc).__name__}). Is it on (battery), running the "
                                         "Wi-Fi sketch, on the same Wi-Fi as this Pi?")


def check_space(cfg):
    target = Path(cfg.record_dir if cfg and cfg.record_dir else "~/truerehab-sessions").expanduser()
    probe = target
    while not probe.exists() and probe != probe.parent:      # the folder is made at the first recording
        probe = probe.parent
    free_gb = shutil.disk_usage(probe).free / 1e9
    report("ok" if free_gb > 2 else "warn", "space for recordings", f"{free_gb:.1f} GB free ({probe}); 1 minute of radar ~ 15 MB")
    temp = Path("/sys/class/thermal/thermal_zone0/temp")
    if temp.exists():
        c = int(temp.read_text()) / 1000
        report("ok" if c < 75 else "warn", "Pi temperature", f"{c:.0f} °C")


def check_running_bridge(cfg, up):
    port = cfg.ws_port if cfg else 8765
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
    up = bridge_running(cfg)
    check_myoware(cfg, up)
    check_space(cfg)
    check_running_bridge(cfg, up)
    fails, warns = RESULTS.count("fail"), RESULTS.count("warn")
    print(f"\n{'PASS' if not fails else 'FAIL'}: {fails} failed, {warns} warnings")
    return 1 if fails else 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    sys.exit(main())
