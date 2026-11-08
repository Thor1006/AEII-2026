"""
A stand-in for the MyoWare board's Wi-Fi link (firmware/myoware_record with WIFI_LINK 1), to test the bridge and
the recorder without the board.

    python fake_myoware.py                  serves tcp://127.0.0.1:3334 until Ctrl+C
    python fake_myoware.py --port 0         any free port (it prints which)
    python fake_myoware.py --pause-every 20 every 20 s it holds its data back for 1.1 s, then sends it all at once:
                                            the Wi-Fi pause the real board shows now and then (--pause-s sets how long)
  then in the bridge's config:  [providers.emg]  enabled = true,  port = "tcp://127.0.0.1:3334"
  or the recorder:              python record.py --emg tcp://127.0.0.1:3334 ...

It talks like the board: its header when a client connects, 1000 "E,<micros>,<raw>,<env>" lines per second in one
packet every 20 ms, "# status ..." every 5 s, one client at a time (a new one replaces the old). Its clock runs from
start-up whether or not anyone listens, like the board's micros().
The signal is FAKE (model/trnet/synth.py, for plumbing tests only): 5 s still, then 2 sets of 8 curls. Each curl is
a burst of muscle activity; rep by rep the envelope grows and the median frequency falls (fatigue). It repeats.
"""
from __future__ import annotations

import argparse
import socket
import sys
import threading
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from truerehab_bridge.repo import use_repo_code  # noqa: E402

HEADER = ("# truerehab-record v2 emg_hz=1000 raw_pin=36 env_pin=39 imu=off link=wifi:3334 fake=fake_myoware.py",
          "# E,micros,raw,env | I,micros,ax,ay,az,gx,gy,gz")
FS = 1000


def fake_signal(seed: int = 1, sets: int = 2, reps: int = 8, still_s: float = 5.0):
    """(raw, env, curls) for one fake session, from the model's fake-data generator: raw and env in ADC counts at
    1 kHz, and each curl's (start_s, end_s)."""
    use_repo_code()
    from trnet import synth
    from trnet.calibrate import load_stats
    rng = np.random.default_rng(seed)
    person = synth.make_person("FAKE", seed)
    plan = synth.Plan(still_s=still_s, shrugs=0, sets=sets, reps_per_set=reps, set_rest_s=10.0)
    tl = synth.plan_timeline(person, plan, rng)
    _, raw, env = synth.emg_samples(person, tl, load_stats(), rng)
    return raw, env, [(r["start"], r["end"]) for r in tl.reps]


class FakeMyoWare:
    """Serves the fake signal on host:port (port 0 = any free port: read .port). speed > 1 runs its clock faster."""

    def __init__(self, host: str = "127.0.0.1", port: int = 3334, seed: int = 1, speed: float = 1.0,
                 boot_us: int = 12_000_000, pause_every: float = 0.0, pause_s: float = 1.1) -> None:
        self.raw, self.env, self.curls = fake_signal(seed)
        self.speed = float(speed)
        self.boot_us = int(boot_us)
        #: Every `pause_every` s (0 = never), hold the data back for `pause_s` s and then send it all: a Wi-Fi pause.
        self.pause_every, self.pause_s = float(pause_every), float(pause_s)
        self.pauses = 0
        self._srv = socket.create_server((host, port))
        self._srv.setblocking(False)
        self.host, self.port = self._srv.getsockname()[:2]
        self._t0 = time.monotonic()
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._client: socket.socket | None = None
        self.clients = 0
        self.lines_sent = 0
        self._thread = threading.Thread(target=self._serve, name="fake-myoware", daemon=True)

    @property
    def url(self) -> str:
        return f"tcp://{self.host}:{self.port}"

    def start(self) -> FakeMyoWare:
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(3)
        self._srv.close()
        self.drop_client()

    def drop_client(self) -> None:
        """Close the current client's connection, as when the board's Wi-Fi drops."""
        with self._lock:
            c, self._client = self._client, None
        if c:
            c.close()

    def samples_made(self) -> int:
        """Samples since start-up: the board samples whether or not anyone listens."""
        return int((time.monotonic() - self._t0) * self.speed * FS)

    def _line(self, i: int) -> str:
        k = i % len(self.raw)
        return f"E,{(self.boot_us + i * 1000) & 0xFFFFFFFF},{self.raw[k]},{self.env[k]}"

    def _status(self, i: int) -> str:
        return (f"# status up_s={(self.boot_us // 1000 + i) // 1000} emg_hz={FS * 1.0:.1f} samples={i} skipped=0 "
                f"wifi=streaming ip=127.0.0.1 rssi_dbm=-52 link_clients={self.clients} link_dropped=0 link_send_fails=0")

    def _serve(self) -> None:
        sent = next_status = 0
        next_pause = time.monotonic() + self.pause_every
        hold_until = 0.0
        while not self._stop.is_set():
            now_m = time.monotonic()
            if self.pause_every > 0 and now_m >= max(next_pause, hold_until):
                hold_until = now_m + self.pause_s
                next_pause = now_m + max(self.pause_every, self.pause_s + 0.1)   # pauses start this far apart
                self.pauses += 1
            if time.monotonic() < hold_until:          # held back by "the network": sent later, nothing lost
                self._stop.wait(0.02)                  # (a new client waits in the queue, as on the board)
                continue
            try:
                conn, _ = self._srv.accept()
            except (BlockingIOError, OSError):
                conn = None
            now = self.samples_made()
            if conn is not None:                       # a new client replaces the old one, like the board
                conn.setblocking(True)
                conn.settimeout(2.0)
                conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                with self._lock:
                    old, self._client = self._client, conn
                    self.clients += 1
                if old:
                    old.close()
                sent, next_status = now, now
                lines = list(HEADER)
            else:
                lines = []
            with self._lock:
                client = self._client
            if client is not None:
                lines += [self._line(i) for i in range(sent, now)]
                sent = now
                if now >= next_status:
                    lines.append(self._status(now))
                    next_status = now + 5 * FS
                try:
                    client.sendall(("\n".join(lines) + "\n").encode())
                    self.lines_sent += len(lines)
                except OSError:                        # the client left, or took nothing for 2 s: drop it
                    with self._lock:
                        if self._client is client:
                            self._client = None
                    client.close()
            self._stop.wait(0.02 / max(1.0, self.speed))


def main() -> int:
    ap = argparse.ArgumentParser(description="Fake MyoWare Wi-Fi link (FAKE sEMG) for testing without the board.")
    ap.add_argument("--host", default="127.0.0.1", help="address to listen on (default 127.0.0.1: this computer only)")
    ap.add_argument("--port", type=int, default=3334, help="TCP port (default 3334, like the board; 0 = any free port)")
    ap.add_argument("--seed", type=int, default=1, help="which fake person")
    ap.add_argument("--pause-every", type=float, default=0.0, metavar="S",
                    help="hold the data back every S seconds, like a Wi-Fi pause (default 0: never)")
    ap.add_argument("--pause-s", type=float, default=1.1, metavar="S", help="how long each pause lasts (default 1.1 s)")
    args = ap.parse_args()
    fake = FakeMyoWare(args.host, args.port, seed=args.seed, pause_every=args.pause_every, pause_s=args.pause_s).start()
    pauses = f", a {args.pause_s:.1f}-s pause every {args.pause_every:.0f} s" if args.pause_every > 0 else ""
    print(f"Fake MyoWare (FAKE sEMG, {len(fake.raw) / FS:.0f}-s loop{pauses}) on {fake.url}. Stop with Ctrl+C.",
          flush=True)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        fake.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
