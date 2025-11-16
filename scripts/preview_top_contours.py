#!/usr/bin/env python3
"""
Preview top-N frames (by contour count) with contour overlays to help tune thresholds.

- Reads a detections CSV (from analyze_streaks.py) to identify frames with the most contours
  and previews those exact frames from the video in descending order of counts.
- Re-computes contours for these frames using the provided thresholding parameters so
  you can see the impact of tuning options live.
- Controls: SPACE/RIGHT to advance, LEFT to go back, Q/ESC to quit.

Usage example:
  python scripts/preview_top_contours.py \
    --video video/GX010063.MP4 \
    --csv data/processed/GX010063_streaks.csv \
    --scale 0.5 --blue-thresh 200 --blur-ksize 3 --min-area 50 --top-n 10 \
    --mask-in data/processed/GX010063_hotmask.png
"""
from __future__ import annotations
import argparse
from pathlib import Path
import io
from typing import List, Tuple

import cv2
import numpy as np
import pandas as pd


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    default_video = repo_root / 'video' / 'GX010063.MP4'
    default_csv = repo_root / 'data' / 'processed' / f'{default_video.stem}_streaks.csv'

    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--video', '-v', type=Path, default=default_video, help='Path to input video')
    p.add_argument('--csv', type=Path, default=default_csv, help='Detections CSV (from analyze_streaks.py)')
    p.add_argument('--mask-in', type=Path, default=None, help='Optional hotspot mask PNG (white=mask)')
    p.add_argument('--scale', type=float, default=0.5, help='Processing scale factor (e.g., 0.5)')
    p.add_argument('--blue-thresh', type=int, default=None, help='Fixed blue threshold (0-255). If None, use Otsu')
    p.add_argument('--blur-ksize', type=int, default=3, help='Gaussian blur kernel size (odd, 0=off)')
    p.add_argument('--min-area', type=float, default=16.0, help='Minimum contour area in pixels (after scaling)')
    p.add_argument('--top-n', type=int, default=10, help='Number of frames to preview (sorted by CSV counts)')
    p.add_argument('--use-bminusg', action='store_true',
                   help='Emphasize blue over green by thresholding (B - G) instead of raw B')
    return p.parse_args()


def load_mask(mask_path: Path | None) -> np.ndarray | None:
    if mask_path is None:
        return None
    m = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
    if m is None:
        raise RuntimeError(f'Failed to read mask: {mask_path}')
    return (m > 0).astype(np.uint8) * 255


def threshold_blue(img_bgr: np.ndarray, blue_thresh: int | None, blur_ksize: int, use_bminusg: bool) -> np.ndarray:
    if use_bminusg:
        blue = img_bgr[:, :, 0].astype(np.int16)
        green = img_bgr[:, :, 1].astype(np.int16)
        target = np.clip(blue - green, 0, 255).astype(np.uint8)
    else:
        target = img_bgr[:, :, 0]
    if blur_ksize and blur_ksize > 0:
        k = blur_ksize if blur_ksize % 2 == 1 else blur_ksize + 1
        target = cv2.GaussianBlur(target, (k, k), 0)
    if blue_thresh is None:
        _, bw = cv2.threshold(target, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    else:
        _, bw = cv2.threshold(target, int(blue_thresh), 255, cv2.THRESH_BINARY)
    return bw


def detect_contours(bw: np.ndarray, min_area: float) -> List[np.ndarray]:
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    clean = cv2.morphologyEx(bw, cv2.MORPH_OPEN, kernel, iterations=1)
    contours, _ = cv2.findContours(clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    out = []
    for c in contours:
        area = cv2.contourArea(c)
        if area < min_area:
            continue
        out.append(c)
    return out


def resize_to_scale(frame: np.ndarray, scale: float) -> np.ndarray:
    if scale == 1.0:
        return frame
    return cv2.resize(frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)


def get_top_frames_from_csv(csv_path: Path, top_n: int) -> Tuple[List[int], dict]:
    # Robustly read table: skip preamble until 'frame,'
    with open(csv_path, 'r') as f:
        lines = f.readlines()
    header_idx = 0
    for i, line in enumerate(lines[:200]):
        if line.lower().startswith('frame,'):
            header_idx = i
            break
    df = pd.read_csv(io.StringIO(''.join(lines[header_idx:])))
    per_frame = df.groupby('frame').size().rename('count').reset_index()
    per_frame = per_frame.sort_values(['count', 'frame'], ascending=[False, True]).reset_index(drop=True)
    top_df = per_frame.head(top_n)
    top_frames = top_df['frame'].astype(int).tolist()
    csv_counts = {int(r['frame']): int(r['count']) for _, r in top_df.iterrows()}
    return top_frames, csv_counts


def main() -> int:
    args = parse_args()

    if not args.csv.exists():
        raise FileNotFoundError(f'Detections CSV not found: {args.csv}')
    if not args.video.exists():
        raise FileNotFoundError(f'Video not found: {args.video}')

    # Determine which frames to preview
    top_frames, csv_counts = get_top_frames_from_csv(args.csv, args.top_n)
    if len(top_frames) == 0:
        print('No frames found in CSV to preview.')
        return 0

    cap = cv2.VideoCapture(str(args.video))
    if not cap.isOpened():
        raise RuntimeError(f'Cannot open video: {args.video}')

    mask = load_mask(args.mask_in)

    idx = 0
    total = len(top_frames)
    win = 'Top-Contours Preview (SPACE/RIGHT next, LEFT prev, Q/ESC quit)'
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)

    while 0 <= idx < total:
        frame_idx = int(top_frames[idx])
        # Seek and grab frame
        cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, frame_idx))
        ret, frame = cap.read()
        if not ret:
            print(f'Failed to read frame {frame_idx}; skipping')
            idx += 1
            continue

        # Prepare view: scale and zero red for consistency with analyzer visuals
        frame_vis = resize_to_scale(frame, args.scale).copy()
        frame_proc = frame_vis.copy()
        frame_proc[:, :, 2] = 0  # zero red channel

        # Apply mask (blackout) in the same coordinate space if provided
        if mask is not None:
            mask_resized = cv2.resize(mask, (frame_proc.shape[1], frame_proc.shape[0]), interpolation=cv2.INTER_NEAREST)
            frame_proc[mask_resized > 0] = 0

        # Compute contours with current params
        bw = threshold_blue(frame_proc, args.blue_thresh, args.blur_ksize, args.use_bminusg)
        contours = detect_contours(bw, args.min_area)

        # Draw contours and boxes in pure red for maximum visibility
        disp = frame_vis.copy()
        for c in contours:
            cv2.drawContours(disp, [c], -1, (0, 0, 255), 3)
            x, y, w, h = cv2.boundingRect(c)
            cv2.rectangle(disp, (x, y), (x + w, y + h), (0, 0, 255), 2)
            m = cv2.moments(c)
            if m['m00'] != 0:
                cx = int(m['m10'] / m['m00'])
                cy = int(m['m01'] / m['m00'])
                cv2.circle(disp, (cx, cy), 4, (0, 0, 255), -1)

        # Title with counts (CSV vs current)
        csv_count = csv_counts.get(frame_idx, 0)
        cur_count = len(contours)
        title = f'Frame {frame_idx}  CSV:{csv_count}  Current:{cur_count}  [{idx+1}/{total}]'
        cv2.setWindowTitle(win, f'{win} — {title}')

        cv2.imshow(win, disp)
        # Wait for key: space/RIGHT=next, LEFT=prev, q/ESC=quit
        key = cv2.waitKey(0) & 0xFF
        if key in (ord('q'), 27):  # q or ESC
            break
        elif key in (ord(' '), 2555904, 83):  # space or RIGHT (Windows/Linux may map differently)
            idx += 1
        elif key in (2424832, 81):  # LEFT
            idx -= 1
        else:
            # default next on any key
            idx += 1

    cap.release()
    cv2.destroyAllWindows()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
