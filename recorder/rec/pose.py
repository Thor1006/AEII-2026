"""Video pose (ground truth only; the product stays camera-free): camera -> MediaPipe -> pose.csv.

pose.csv: t_ns, frame, person, then for each of the 33 MediaPipe landmarks
  i{k}_x, i{k}_y, i{k}_z, i{k}_v   image coordinates (x, y in 0..1 of the frame) + visibility
  w{k}_x, w{k}_y, w{k}_z           world coordinates in metres, origin between the hips, y down
Empty cells when no person was found. Joint angles are computed from the world points (`angles`).
"""
import csv
import time
from pathlib import Path

import numpy as np

from .sources import Source

N_LM = 33
MODEL = Path(__file__).resolve().parents[1] / "models" / "pose_landmarker_full.task"
LM = {"nose": 0, "l_ear": 7, "r_ear": 8, "l_shoulder": 11, "r_shoulder": 12, "l_elbow": 13, "r_elbow": 14,
      "l_wrist": 15, "r_wrist": 16, "l_hip": 23, "r_hip": 24}
BONES = [(11, 12), (11, 13), (13, 15), (12, 14), (14, 16), (11, 23), (12, 24), (23, 24), (7, 11), (8, 12)]
HEADER = ["t_ns", "frame", "person"] + [f"i{k}_{a}" for k in range(N_LM) for a in "xyzv"] \
    + [f"w{k}_{a}" for k in range(N_LM) for a in "xyz"]


class PoseEstimator:
    """MediaPipe PoseLandmarker in video mode (it tracks between frames)."""

    def __init__(self, model=MODEL):
        import mediapipe as mp
        from mediapipe.tasks import python as mpt
        from mediapipe.tasks.python import vision
        if not Path(model).exists():
            raise FileNotFoundError(f"{model} missing: see recorder/README.md (pose model download)")
        self.mp = mp
        self.lm = vision.PoseLandmarker.create_from_options(vision.PoseLandmarkerOptions(
            base_options=mpt.BaseOptions(model_asset_path=str(model)),
            running_mode=vision.RunningMode.VIDEO, num_poses=1))
        self.last_ms = -1

    def __call__(self, bgr, t_ms):
        """-> (image [33, 4], world [33, 3]) or (None, None) if no person."""
        t_ms = max(int(t_ms), self.last_ms + 1)  # MediaPipe needs strictly increasing timestamps
        self.last_ms = t_ms
        rgb = np.ascontiguousarray(bgr[:, :, ::-1])
        r = self.lm.detect_for_video(self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=rgb), t_ms)
        if not r.pose_landmarks:
            return None, None
        img = np.array([[p.x, p.y, p.z, p.visibility] for p in r.pose_landmarks[0]])
        world = np.array([[p.x, p.y, p.z] for p in r.pose_world_landmarks[0]])
        return img, world

    def close(self):
        self.lm.close()


def open_camera(index, width=1280, height=720, fps=30):
    import cv2
    cap = cv2.VideoCapture(index, cv2.CAP_AVFOUNDATION)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, fps)
    ok = cap.isOpened()
    for _ in range(30):  # the first frames can take a moment (Continuity Camera connects wirelessly)
        if ok and cap.read()[0]:
            return cap
        time.sleep(0.1)
    cap.release()
    raise RuntimeError(f"camera {index}: no picture. Check the index (pose_check.py --list) and that this "
                       "app may use the camera (System Settings > Privacy & Security > Camera).")


def draw(bgr, img_lm, lines=()):
    """Skeleton and text on a frame, for the preview and snapshots."""
    import cv2
    h, w = bgr.shape[:2]
    if img_lm is not None:
        pts = [(int(x * w), int(y * h)) for x, y, _, _ in img_lm]
        for a, b in BONES:
            cv2.line(bgr, pts[a], pts[b], (80, 220, 255), 3, cv2.LINE_AA)
        for k in set(sum(BONES, ())):
            cv2.circle(bgr, pts[k], 5, (255, 255, 255), -1, cv2.LINE_AA)
    for i, text in enumerate(lines):
        cv2.putText(bgr, text, (16, 34 + 30 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 4, cv2.LINE_AA)
        cv2.putText(bgr, text, (16, 34 + 30 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 1, cv2.LINE_AA)
    return bgr


# ---------------------------------------------------------------- angles (pure numpy)

def _angle(u, v):
    cos = np.sum(u * v, -1) / (np.linalg.norm(u, axis=-1) * np.linalg.norm(v, axis=-1) + 1e-12)
    return np.degrees(np.arccos(np.clip(cos, -1, 1)))


def angles(world):
    """Joint angles from world landmarks [n, 33, 3] (metres, y down). Candidates for labels, not clinical values.

    elbow_l / elbow_r      angle at the elbow, 180 = straight arm
    trunk_lean             hip-centre -> shoulder-centre vs straight up, any direction (deg)
    trunk_lean_side        sideways part (+ = towards image right)
    trunk_lean_fwd         towards/away from the camera; single-camera depth is rough
    ear_shoulder_l / _r    vertical ear-to-shoulder gap (m); a shrug (shoulder elevation) makes it smaller
    """
    w = np.asarray(world, dtype=float)
    if w.ndim == 2:
        w = w[None]
    p = {k: w[:, i] for k, i in LM.items()}
    up = np.array([0.0, -1.0, 0.0])
    trunk = (p["l_shoulder"] + p["r_shoulder"]) / 2 - (p["l_hip"] + p["r_hip"]) / 2
    return {
        "elbow_l": _angle(p["l_shoulder"] - p["l_elbow"], p["l_wrist"] - p["l_elbow"]),
        "elbow_r": _angle(p["r_shoulder"] - p["r_elbow"], p["r_wrist"] - p["r_elbow"]),
        "trunk_lean": _angle(trunk, np.broadcast_to(up, trunk.shape)),
        "trunk_lean_side": np.degrees(np.arctan2(trunk[:, 0], -trunk[:, 1])),
        "trunk_lean_fwd": np.degrees(np.arctan2(trunk[:, 2], -trunk[:, 1])),
        "ear_shoulder_l": p["l_shoulder"][:, 1] - p["l_ear"][:, 1],
        "ear_shoulder_r": p["r_shoulder"][:, 1] - p["r_ear"][:, 1],
    }


# ---------------------------------------------------------------- recorder source

def read_frame(cap, halt=None, give_up_s=3.0, nap_s=0.01):
    """The camera's next frame (BGR), or None once halt is set. Between failed reads it naps instead of spinning at
    full speed next to the radar thread; a camera that sends nothing for give_up_s (unplugged, or another app took
    it) raises, so the status line shows pose ERROR and the other sensors keep recording."""
    t0 = time.perf_counter()
    while halt is None or not halt.is_set():
        ok, bgr = cap.read()
        if ok:
            return bgr
        if time.perf_counter() - t0 > give_up_s:
            raise RuntimeError(f"the camera sent no picture for {give_up_s:.0f} s (unplugged, or taken by another app?)")
        time.sleep(nap_s)
    return None


class PoseSource(Source):
    """Camera frames -> MediaPipe pose -> pose.csv, stamped with the session clock on arrival."""

    unit = " fps"

    def __init__(self, session, camera, model=MODEL, save_video=False, width=1280, height=720, fps=30):
        super().__init__(session, "pose")
        self.cap = open_camera(camera, width, height, fps)
        self.est = PoseEstimator(model)
        self.file = open(session.dir / "pose.csv", "w", newline="")
        self.out = csv.writer(self.file)
        self.out.writerow(HEADER)
        self.with_person = 0
        self.writer = None
        if save_video:
            import cv2
            w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self.writer = cv2.VideoWriter(str(session.dir / "video.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))

    def loop(self):
        frame_no, last_flush = 0, time.perf_counter()
        while not self.halt.is_set():
            bgr = read_frame(self.cap, self.halt)
            if bgr is None:
                break
            t = self.session.t()
            img, world = self.est(bgr, t / 1e6)
            if self.writer is not None:
                self.writer.write(bgr)  # frame number in pose.csv = frame index in video.mp4
            if img is None:
                self.out.writerow([t, frame_no, 0])
            else:
                self.with_person += 1
                self.out.writerow([t, frame_no, 1] + [f"{v:.5f}" for v in img.ravel()]
                                  + [f"{v:.5f}" for v in world.ravel()])
            frame_no += 1
            self._tick(t)
            if time.perf_counter() - last_flush > 0.5:
                self.file.flush()
                last_flush = time.perf_counter()

    def status(self):
        s = super().status()
        return s if self.error or not self.count else s + f" (person {100 * self.with_person // self.count}%)"

    def close(self):
        self.cap.release()
        if self.writer is not None:
            self.writer.release()
        self.est.close()
        self.file.close()

    def summary(self):
        return {"frames": self.count, "with_person": self.with_person, "error": self.error}
