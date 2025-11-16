#!/usr/bin/env python3
"""
Analyze blue bioluminescent streaks in a video and export detections to CSV.

Pipeline (per frame):
- Optionally rescale
- Remove red channel (view is Blue+Green; detection uses Blue by default)
- Optionally apply hotspot mask (blackout)
- Pre-blur and threshold (fixed or Otsu) on blue channel
- Morphological clean-up and contour detection
- Emit per-contour rows: frame, time (s), cx, cy, area, bbox

Outputs: CSV (default: data/processed/<video>_streaks.csv)
"""
from __future__ import annotations
import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional, Tuple

import cv2
import numpy as np


@dataclass
class VideoProps:
    fps: float
    width: int
    height: int
    frames: int


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    default_video = repo_root / 'video' / 'GX010063.MP4'
    default_out = repo_root / 'data' / 'processed' / f'{default_video.stem}_streaks.csv'

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--video', '-v', type=Path, default=default_video, help='Path to input video')
    p.add_argument('--output', '-o', type=Path, default=default_out, help='Output CSV path')
    p.add_argument('--mask-in', type=Path, default=None, help='Optional hotspot mask PNG (white=mask)')
    p.add_argument('--scale', type=float, default=0.5, help='Processing scale factor (e.g., 0.5)')
    p.add_argument('--blue-thresh', type=int, default=None, help='Fixed blue threshold (0-255). If None, use Otsu')
    p.add_argument('--blur-ksize', type=int, default=3, help='Gaussian blur kernel size (odd, 0=off)')
    p.add_argument('--min-area', type=float, default=16.0, help='Minimum contour area in pixels (after scaling)')
    p.add_argument('--use-bminusg', action='store_true',
                   help='Emphasize blue over green by thresholding (B - G) instead of raw B')
    p.add_argument('--max-frames', type=int, default=None, help='Limit number of frames for quick runs')
    p.add_argument('--seconds-per-frame', type=float, default=None,
                   help='Override seconds per frame for timelapse (if given, time_s = frame * value; else use 1/FPS)')
    p.add_argument('--roi-thirds', action='store_true',
                   help='Label detections by vertical thirds: left/middle/right')
    p.add_argument('--roi-config', type=Path, default=None,
                   help='Path to ROI JSON (from define_rois.py). Overrides --roi-thirds labeling.')
    p.add_argument('--restrict-to-roi', action='store_true',
                   help='If provided with --roi-config, only keep detections inside any ROI')
    p.add_argument('--verbose', action='store_true', help='Print per-frame progress')
    return p.parse_args()


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def open_video(path: Path) -> Tuple[cv2.VideoCapture, VideoProps]:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f'Cannot open video: {path}')
    fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    return cap, VideoProps(fps=fps if fps > 0 else 30.0, width=width, height=height, frames=frames)


def load_rois(roi_path: Optional[Path]) -> Optional[dict]:
    if roi_path is None:
        return None
    data = None
    with open(roi_path, 'r') as f:
        import json
        data = json.load(f)
    # expect keys: original_size{width,height}, rects[{label,x,y,w,h}]
    return data


def load_mask(mask_path: Optional[Path]) -> Optional[np.ndarray]:
    if mask_path is None:
        return None
    m = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
    if m is None:
        raise RuntimeError(f'Failed to read mask: {mask_path}')
    return (m > 0).astype(np.uint8) * 255


def iter_frames(cap: cv2.VideoCapture, scale: float) -> Iterator[np.ndarray]:
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if scale != 1.0:
            frame = cv2.resize(frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        yield frame


def threshold_blue(img_bgr: np.ndarray, blue_thresh: Optional[int], blur_ksize: int, use_bminusg: bool) -> np.ndarray:
    if use_bminusg:
        # Compute (B - G) to reduce false positives from greenish/red bleed
        blue = img_bgr[:, :, 0].astype(np.int16)
        green = img_bgr[:, :, 1].astype(np.int16)
        diff = np.clip(blue - green, 0, 255).astype(np.uint8)
        target = diff
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


def detect_contours(bw: np.ndarray, min_area: float) -> Iterator[Tuple[np.ndarray, float, Tuple[int,int,int,int]]]:
    # Morph open to clean speckle
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    clean = cv2.morphologyEx(bw, cv2.MORPH_OPEN, kernel, iterations=1)
    contours, _ = cv2.findContours(clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in contours:
        area = cv2.contourArea(c)
        if area < min_area:
            continue
        x, y, w, h = cv2.boundingRect(c)
        yield c, area, (x, y, w, h)


def contour_centroid(cnt: np.ndarray) -> Tuple[float, float]:
    m = cv2.moments(cnt)
    if m['m00'] == 0:
        x, y, w, h = cv2.boundingRect(cnt)
        return float(x + w / 2.0), float(y + h / 2.0)
    return float(m['m10'] / m['m00']), float(m['m01'] / m['m00'])


def main() -> int:
    args = parse_args()
    ensure_parent(args.output)

    cap, props = open_video(args.video)
    mask = load_mask(args.mask_in)
    roi_cfg = load_rois(args.roi_config)

    # write header
    with open(args.output, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['video', 'width', 'height', 'scale', 'fps'])
        w.writerow([str(args.video), props.width, props.height, args.scale, props.fps])
        w.writerow([])
        w.writerow(['frame', 'time_s', 'region', 'cx', 'cy', 'area', 'bbox_x', 'bbox_y', 'bbox_w', 'bbox_h'])

        frame_idx = 0
        total = 0
        for frame in iter_frames(cap, args.scale):
            if args.max_frames is not None and frame_idx >= args.max_frames:
                break

            # zero red channel for conceptual consistency
            frame[:, :, 2] = 0

            # apply mask if given
            if mask is not None:
                if mask.shape[:2] != frame.shape[:2]:
                    mask_resized = cv2.resize(mask, (frame.shape[1], frame.shape[0]), interpolation=cv2.INTER_NEAREST)
                else:
                    mask_resized = mask
                frame[mask_resized > 0] = 0

            bw = threshold_blue(frame, args.blue_thresh, args.blur_ksize, args.use_bminusg)
            # Prepare ROI mapping per frame size
            rects_scaled = None
            if roi_cfg is not None:
                W0 = int(roi_cfg['original_size']['width'])
                H0 = int(roi_cfg['original_size']['height'])
                Wf, Hf = frame.shape[1], frame.shape[0]
                sx = Wf / float(W0) if W0 > 0 else 1.0
                sy = Hf / float(H0) if H0 > 0 else 1.0
                rects_scaled = [
                    {
                        'label': r['label'],
                        'x': int(round(r['x'] * sx)),
                        'y': int(round(r['y'] * sy)),
                        'w': int(round(r['w'] * sx)),
                        'h': int(round(r['h'] * sy)),
                    }
                    for r in roi_cfg['rects']
                ]

            # region labeling by thirds if requested and no ROI config
            region = 'all'
            use_thirds = (roi_cfg is None and args.roi_thirds)
            if use_thirds:
                W = frame.shape[1]
                one_third = W / 3.0
                # define a function to map x to region label
                def region_label(xc: float) -> str:
                    if xc < one_third:
                        return 'left'
                    elif xc < 2*one_third:
                        return 'middle'
                    else:
                        return 'right'
            else:
                # define ROI-based region labeler
                def region_label(xc: float, yc: float) -> str:
                    if not rects_scaled:
                        return 'all'
                    for r in rects_scaled:
                        if (xc >= r['x'] and xc < r['x'] + r['w'] and yc >= r['y'] and yc < r['y'] + r['h']):
                            return r['label']
                    return 'outside'

            for cnt, area, (x, y, wbox, hbox) in detect_contours(bw, args.min_area):
                cx, cy = contour_centroid(cnt)
                # compute time using override if provided
                if args.seconds_per_frame is not None and args.seconds_per_frame > 0:
                    t = frame_idx * float(args.seconds_per_frame)
                else:
                    t = frame_idx / props.fps
                # assign region label
                if use_thirds:
                    region = region_label(cx)
                else:
                    region = region_label(cx, cy)
                if roi_cfg is not None and args.restrict_to_roi and region == 'outside':
                    continue
                w.writerow([frame_idx, f'{t:.6f}', region, f'{cx:.2f}', f'{cy:.2f}', f'{area:.2f}', x, y, wbox, hbox])
                total += 1

            if args.verbose and (frame_idx % 60 == 0):
                print(f'Processed frame {frame_idx} / ~{props.frames} (detections so far: {total})')

            frame_idx += 1

    cap.release()
    print(f'Done. Wrote detections to {args.output}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
