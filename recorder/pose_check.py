"""Set up the camera for video pose before recording.

  .venv/bin/python pose_check.py --list            # which camera numbers exist (and their picture size)
  .venv/bin/python pose_check.py --camera 1        # live preview: skeleton, joint angles, fps (q to quit)
  .venv/bin/python pose_check.py --camera 1 --snapshot check.png   # one annotated picture, no window

Continuity Camera (iPhone): turn OFF Center Stage, Portrait, Studio Light and Desk View
(Control Center > Video Effects), put the phone on a tripod in landscape, same spot every session.
"""
import argparse
import time

import cv2
import numpy as np

from rec.pose import PoseEstimator, angles, draw, open_camera


def list_cameras(max_index=6):
    found = False
    for i in range(max_index):
        cap = cv2.VideoCapture(i, cv2.CAP_AVFOUNDATION)
        if not cap.isOpened():
            cap.release()
            continue
        t0, n, size = time.perf_counter(), 0, None
        while time.perf_counter() - t0 < 1.5:
            ok, f = cap.read()
            if ok:
                n += 1
                size = f.shape[1], f.shape[0]
        cap.release()
        if size:
            found = True
            print(f"camera {i}: {size[0]}x{size[1]}, about {n / 1.5:.0f} fps")
    if not found:
        print("No camera gave a picture. Allow camera access for this app in System Settings > "
              "Privacy & Security > Camera, and for the iPhone keep it near the Mac, locked, on a stand.")


def label_lines(world, fps, person_pct):
    lines = [f"{fps:4.1f} fps   person {person_pct:3.0f}%"]
    if world is not None:
        a = {k: float(v[0]) for k, v in angles(world).items()}
        lines += [f"elbow L {a['elbow_l']:5.1f}  R {a['elbow_r']:5.1f} deg",
                  f"trunk lean {a['trunk_lean']:4.1f} deg (side {a['trunk_lean_side']:+5.1f})",
                  f"ear-shoulder L {100 * a['ear_shoulder_l']:4.1f}  R {100 * a['ear_shoulder_r']:4.1f} cm"]
    return lines


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--list", action="store_true")
    p.add_argument("--camera", type=int)
    p.add_argument("--snapshot", metavar="PNG", help="save one annotated frame after ~3 s, no window")
    args = p.parse_args()
    if args.list or args.camera is None:
        list_cameras()
        return

    cap = open_camera(args.camera)
    est = PoseEstimator()
    t0 = time.perf_counter()
    times, seen, total = [], 0, 0
    try:
        while True:
            ok, bgr = cap.read()
            if not ok:
                continue
            now = time.perf_counter()
            img, world = est(bgr, (now - t0) * 1000)
            times = [t for t in times if t > now - 2] + [now]
            total += 1
            seen += img is not None
            frame = draw(bgr, img, label_lines(world, (len(times) - 1) / max(times[-1] - times[0], 1e-6),
                                               100 * seen / total))
            if args.snapshot:
                if now - t0 > 3:
                    cv2.imwrite(args.snapshot, frame)
                    print(f"Saved {args.snapshot}  ({(len(times) - 1) / 2:.0f} fps, person in {100 * seen / total:.0f}% of frames)")
                    return
                continue
            cv2.imshow("pose check (q to quit)", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                return
    finally:
        cap.release()
        est.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
