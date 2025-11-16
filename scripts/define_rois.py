#!/usr/bin/env python3
"""
Interactively define rectangular ROIs on a video frame and save to JSON.

- Opens a window with a selected frame (default: frame 0) at a given scale.
- Use the mouse to draw multiple rectangles (uses OpenCV selectROIs).
- If exactly 3 rectangles are selected, they will be auto-labeled left/middle/right
  based on x center. Otherwise you can provide labels or they will be auto-named.
- Saves JSON to data/config/<video>_rois.json by default and an overlay preview PNG.

Non-interactive alternative:
- Pass --rect label:x,y,w,h multiple times to specify rectangles directly (in ORIGINAL pixels).

Controls in the selection window (OpenCV UI):
- Draw rectangles with the mouse; press ENTER or SPACE to confirm selection.
- Press ESC to cancel.
"""
from __future__ import annotations
import argparse
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Tuple, Optional

import cv2
import numpy as np


@dataclass
class Rect:
    label: str
    x: int
    y: int
    w: int
    h: int


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    default_video = repo_root / 'video' / 'GX010063.MP4'

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--video', '-v', type=Path, default=default_video, help='Path to input video')
    p.add_argument('--frame-index', type=int, default=0, help='Frame index to grab for selection')
    p.add_argument('--scale', type=float, default=0.5, help='Display scale (e.g., 0.5 to halve size)')
    # If not provided, the output path will be derived from the --video argument later
    p.add_argument('--output', '-o', type=Path, default=None, help='Output JSON path')
    p.add_argument('--preview', type=Path, default=None, help='Optional path to save overlay preview PNG')
    p.add_argument('--rect', action='append', default=None,
                   help='Add rectangle in ORIGINAL pixels as label:x,y,w,h (can be repeated)')
    return p.parse_args()


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def grab_frame(video_path: Path, frame_index: int) -> np.ndarray:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f'Cannot open video: {video_path}')
    cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, frame_index))
    ret, frame = cap.read()
    cap.release()
    if not ret:
        raise RuntimeError(f'Failed to read frame {frame_index} from {video_path}')
    return frame


def select_rois_interactive(frame_bgr: np.ndarray, scale: float) -> List[Tuple[int, int, int, int]]:
    disp = frame_bgr
    if scale != 1.0:
        disp = cv2.resize(frame_bgr, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    # OpenCV selectROIs returns Nx4 array [[x,y,w,h], ...]
    rois = cv2.selectROIs('Select ROIs (ENTER=OK, ESC=Cancel)', disp, showCrosshair=True, fromCenter=False)
    cv2.destroyAllWindows()
    rois = np.array(rois, dtype=np.int32)
    if rois.size == 0:
        return []
    if scale != 1.0:
        rois = (rois.astype(np.float32) / float(scale)).round().astype(np.int32)
    return [(int(x), int(y), int(w), int(h)) for (x, y, w, h) in rois]


def auto_labels_from_order(rects: List[Tuple[int,int,int,int]]) -> List[str]:
    # Order by x center
    ordered = sorted([(x + w / 2.0, i) for i, (x, y, w, h) in enumerate(rects)])
    labels = ['left', 'middle', 'right']
    out = [None] * len(rects)
    for lbl, (_, idx) in zip(labels, ordered):
        out[idx] = lbl
    # Fill any remaining with roi_#
    for i in range(len(out)):
        if out[i] is None:
            out[i] = f'roi_{i+1}'
    return out


def parse_rect_arg(arg: str) -> Rect:
    # label:x,y,w,h
    try:
        label, rest = arg.split(':', 1)
        x, y, w, h = map(int, rest.split(','))
        return Rect(label=label, x=x, y=y, w=w, h=h)
    except Exception:
        raise SystemExit(f'Invalid --rect value: {arg}. Expected label:x,y,w,h')


def draw_overlay(img: np.ndarray, rects: List[Rect]) -> np.ndarray:
    out = img.copy()
    for r in rects:
        cv2.rectangle(out, (r.x, r.y), (r.x + r.w, r.y + r.h), (0, 255, 255), 2)
        cv2.putText(out, r.label, (r.x, max(0, r.y - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2, cv2.LINE_AA)
    return out


def main() -> int:
    args = parse_args()
    # Derive output path from the provided video if not explicitly set
    if args.output is None:
        out_dir = Path(__file__).resolve().parents[1] / 'data' / 'config'
        args.output = out_dir / f'{Path(args.video).stem}_rois.json'
    ensure_parent(args.output)

    frame = grab_frame(args.video, args.frame_index)
    H, W = frame.shape[:2]

    rects: List[Rect] = []
    if args.rect:
        # Non-interactive: use provided rectangles in original pixels
        rects = [parse_rect_arg(s) for s in args.rect]
    else:
        # Interactive: use OpenCV selection on a scaled view
        rois = select_rois_interactive(frame, args.scale)
        if len(rois) == 0:
            print('No ROIs selected; nothing to save.')
            return 1
        if len(rois) == 3:
            labels = auto_labels_from_order(rois)
        else:
            labels = [f'roi_{i+1}' for i in range(len(rois))]
        for lbl, (x, y, w, h) in zip(labels, rois):
            rects.append(Rect(label=lbl, x=int(x), y=int(y), w=int(w), h=int(h)))

    data = {
        'video': str(args.video),
        'frame_index': int(args.frame_index),
        'original_size': {'width': int(W), 'height': int(H)},
        'scale_used_for_selection': float(args.scale),
        'rects': [asdict(r) for r in rects],
    }

    with open(args.output, 'w') as f:
        json.dump(data, f, indent=2)
    print(f'Saved ROI config to {args.output}')

    # Save overlay preview
    preview_path = args.preview
    if preview_path is None:
        preview_dir = Path(__file__).resolve().parents[1] / 'figures'
        preview_path = preview_dir / f'{Path(args.output).stem}_overlay.png'
    ensure_parent(preview_path)

    overlay = draw_overlay(frame, rects)
    if args.scale != 1.0:
        overlay = cv2.resize(overlay, None, fx=args.scale, fy=args.scale, interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(preview_path), overlay)
    print(f'Saved overlay preview to {preview_path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
