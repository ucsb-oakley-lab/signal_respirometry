#!/usr/bin/env python3
"""
Preview contours from a detections CSV overlaid on the video, showing ONLY detections inside ROI.

Inputs:
  --video <path>          Input video file.
  --csv <path>            Detections CSV from analyze_streaks.py (with preamble).
  --roi-config <path>     ROI JSON created by scripts/define_rois.py.

Optional:
  --scale <float>         Display/detection scale (defaults to value parsed from CSV preamble, else 1.0).
  --line-thickness <int>  Overlay line thickness for boxes (default 4).
  --show-roi              Draw ROI rectangles for context (default off).
  --play                  Autoplay video at ~original FPS (Space toggles pause; default paused).
  --annotate-labels       Draw ROI label letter next to each box (default on; disable with --no-annotate-labels).
  --start <int>           Start at this frame index (default 0).

Controls:
  - SPACE: play/pause
  - RIGHT: next frame
  - LEFT:  previous frame
  - R:     toggle ROI rectangle overlay
  - Q/ESC: quit

Note: CSV coordinates and ROI are reconciled by scaling ROI rectangles to the detection scale.
"""
from __future__ import annotations
import argparse
import io
import json
from pathlib import Path
from typing import Dict, List

import cv2
import numpy as np
import pandas as pd


def parse_args():
    p = argparse.ArgumentParser(description="Preview detections inside ROI over video")
    p.add_argument("--video", required=True, type=str)
    p.add_argument("--csv", required=True, type=str)
    p.add_argument("--roi-config", required=True, type=str)
    p.add_argument("--scale", type=float, default=None, help="Detection/display scale; default parsed from CSV preamble or 1.0")
    p.add_argument("--line-thickness", type=int, default=4)
    p.add_argument("--show-roi", action="store_true")
    p.add_argument("--play", action="store_true")
    p.add_argument("--annotate-labels", dest="annotate_labels", action="store_true")
    p.add_argument("--no-annotate-labels", dest="annotate_labels", action="store_false")
    p.set_defaults(annotate_labels=True)
    p.add_argument("--start", type=int, default=0)
    return p.parse_args()


def read_csv_with_preamble(csv_path: Path) -> pd.DataFrame:
    with open(csv_path, "r") as f:
        lines = f.readlines()
    header_idx = 0
    for i, line in enumerate(lines[:200]):
        if line.lower().startswith("frame,"):
            header_idx = i
            break
    df = pd.read_csv(io.StringIO("".join(lines[header_idx:])))
    return df, lines


def parse_scale_from_preamble(preamble_lines: List[str]) -> float:
    # Attempt to parse scale from second line of preamble (as used in the notebook helper)
    try:
        if len(preamble_lines) > 1:
            vals = preamble_lines[1].strip().split(",")
            if len(vals) >= 4:
                return float(vals[3])
    except Exception:
        pass
    return 1.0


def load_and_scale_rois(roi_json_path: Path, scale: float):
    with open(roi_json_path, "r") as f:
        roi_cfg = json.load(f)
    rects = roi_cfg["rects"]
    scaled = []
    for r in rects:
        scaled.append({
            "label": r["label"],
            "x": int(round(r["x"] * scale)),
            "y": int(round(r["y"] * scale)),
            "w": int(round(r["w"] * scale)),
            "h": int(round(r["h"] * scale)),
        })
    return scaled


def point_in_rect(px: float, py: float, r: Dict) -> bool:
    return (px >= r["x"] and px < r["x"] + r["w"] and py >= r["y"] and py < r["y"] + r["h"]) \
        if r["w"] > 0 and r["h"] > 0 else False


def group_by_frame(df: pd.DataFrame) -> Dict[int, pd.DataFrame]:
    grouped = {}
    if len(df) == 0:
        return grouped
    for frame_idx, rows in df.groupby("frame"):
        grouped[int(frame_idx)] = rows
    return grouped


def main():
    args = parse_args()
    video_path = Path(args.video)
    csv_path = Path(args.csv)
    roi_json_path = Path(args.roi_config)

    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")
    if not roi_json_path.exists():
        raise FileNotFoundError(f"ROI JSON not found: {roi_json_path}")

    df, preamble = read_csv_with_preamble(csv_path)
    # Ensure required columns exist
    required_cols = {"frame", "cx", "cy", "bbox_x", "bbox_y", "bbox_w", "bbox_h"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"CSV missing required columns: {sorted(missing)}")

    scale = args.scale if args.scale is not None else parse_scale_from_preamble(preamble)
    scaled_rois = load_and_scale_rois(roi_json_path, scale)

    by_frame = group_by_frame(df)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    delay_ms = int(1000 / fps) if fps and fps > 0 else 33

    current = max(0, min(args.start, total_frames - 1))
    paused = not args.play
    show_roi = args.show_roi

    win = "ROI-only preview"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)

    # Colors
    YELLOW = (0, 255, 255)
    ROI_COLOR = (255, 255, 255)  # white
    TEXT_COLOR = (200, 200, 200)

    def goto_frame(idx: int):
        nonlocal current
        current = max(0, min(idx, total_frames - 1))
        cap.set(cv2.CAP_PROP_POS_FRAMES, current)

    goto_frame(current)

    while True:
        if not paused or True:  # We still need to fetch current frame on step changes
            ok, frame = cap.read()
            if not ok:
                break
            # If cap.read advanced beyond desired (e.g., after goto), ensure sync
            pos = int(cap.get(cv2.CAP_PROP_POS_FRAMES)) - 1
            current = pos

            # Scale frame for display to match detection coords
            h, w = frame.shape[:2]
            disp = cv2.resize(frame, (int(w * scale), int(h * scale))) if scale != 1.0 else frame.copy()

            # Overlay ROI rectangles if requested
            if show_roi:
                for r in scaled_rois:
                    cv2.rectangle(disp, (r["x"], r["y"]), (r["x"] + r["w"], r["y"] + r["h"]), ROI_COLOR, 1)
                    cv2.putText(disp, r["label"], (r["x"] + 4, max(0, r["y"] - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, ROI_COLOR, 1, cv2.LINE_AA)

            # Draw detections in ROI for this frame
            rows = by_frame.get(current)
            drawn = 0
            if rows is not None:
                for _, row in rows.iterrows():
                    cx, cy = float(row["cx"]), float(row["cy"])  # scaled coords
                    in_label = None
                    for r in scaled_rois:
                        if point_in_rect(cx, cy, r):
                            in_label = r["label"]
                            break
                    if in_label is None:
                        continue  # skip outside
                    x, y = int(row["bbox_x"]), int(row["bbox_y"])  # already at scaled coords
                    w, h = int(row["bbox_w"]), int(row["bbox_h"])  # may be 0 if not provided
                    if w > 0 and h > 0:
                        cv2.rectangle(disp, (x, y), (x + w, y + h), YELLOW, args.line_thickness)
                    else:
                        # Fallback to small cross at centroid
                        cv2.drawMarker(disp, (int(round(cx)), int(round(cy))), YELLOW, markerType=cv2.MARKER_CROSS, markerSize=8, thickness=args.line_thickness)
                    if args.annotate_labels and in_label:
                        cv2.putText(disp, in_label, (x, max(0, y - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, YELLOW, 1, cv2.LINE_AA)
                    drawn += 1

            # HUD
            t_s = df.loc[df["frame"] == current, "time_s"].iloc[0] if "time_s" in df.columns and current in by_frame else None
            hud = f"frame {current+1}/{total_frames}  detections in ROI: {drawn}"
            if t_s is not None:
                hud += f"  t={t_s:.2f}s"
            cv2.putText(disp, hud, (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, TEXT_COLOR, 2, cv2.LINE_AA)

            cv2.imshow(win, disp)

        key = cv2.waitKey(0 if paused else delay_ms) & 0xFF
        if key in (ord('q'), 27):  # q or ESC
            break
        elif key == ord(' '):  # space toggle
            paused = not paused
        elif key == ord('r'):
            show_roi = not show_roi
        elif key == 81:  # left arrow
            goto_frame(current - 1)
            paused = True
        elif key == 83:  # right arrow
            goto_frame(current + 1)
            paused = True
        elif key == 82:  # up arrow: skip +30
            goto_frame(current + 30)
            paused = True
        elif key == 84:  # down arrow: skip -30
            goto_frame(current - 30)
            paused = True
        else:
            # No key or unrecognized; if playing, continue; if paused, loop to waitKey again
            pass

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
