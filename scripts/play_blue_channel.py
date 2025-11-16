#!/usr/bin/env python3
"""
Play a video with the red channel removed (showing only Blue + Green) using OpenCV.

By default, looks for ../video/GX010063.MP4 relative to this script.
Use --video to provide a different path.

Controls:
- q or ESC: quit
- SPACE: pause/resume
"""
from __future__ import annotations
import argparse
import sys
import time
from pathlib import Path

import cv2
import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    repo_root = Path(__file__).resolve().parents[1]
    default_video = repo_root / 'video' / 'GX010063.MP4'
    parser.add_argument('--video', '-v', type=Path, default=default_video,
                        help='Path to video file (default: %(default)s)')
    parser.add_argument('--fps-limit', type=float, default=None,
                        help='Limit playback FPS (default: use source FPS if available)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Do not open a window; just print video info and first frame stats')
    parser.add_argument('--scale', type=float, default=1.0,
                        help='Display/process scale factor (e.g., 0.5 to halve resolution)')
    parser.add_argument('--inpaint-radius', type=int, default=3,
                        help='Radius (pixels) for inpaint when applying hotspot masks')
    # Hotspot removal options
    parser.add_argument('--hotspots', default='off', choices=['off', 'auto'],
                        help="Remove persistent bright hotspots (auto = detect via pre-pass)")
    parser.add_argument('--mask-mode', default='inpaint', choices=['inpaint', 'blackout', 'none'],
                        help='How to apply hotspot mask during playback')
    parser.add_argument('--mask-in', type=Path, default=None,
                        help='Optional path to an existing hotspot mask (PNG); overrides auto detection if provided')
    parser.add_argument('--red-thresh', type=int, default=220,
                        help='Threshold (0-255) on red channel used to flag hotspots')
    parser.add_argument('--frac', type=float, default=0.8,
                        help='Fraction of sampled frames a pixel must exceed threshold to be a hotspot')
    parser.add_argument('--stride', type=int, default=60,
                        help='Frame stride for hotspot sampling (e.g., 60 = about 2s apart @30fps)')
    parser.add_argument('--max-samples', type=int, default=300,
                        help='Maximum number of frames to sample for hotspot detection')
    parser.add_argument('--dilate', type=int, default=1,
                        help='Dilation radius (pixels) to expand hotspot mask')
    parser.add_argument('--mask-out', type=Path, default=None,
                        help='Optional path to save the computed hotspot mask (PNG)')
    return parser.parse_args()


def open_capture(path: Path) -> cv2.VideoCapture:
    cap = cv2.VideoCapture(str(path))
    return cap


def get_props(cap: cv2.VideoCapture) -> dict:
    props = {
        'fps': cap.get(cv2.CAP_PROP_FPS) or 0.0,
        'frame_count': int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0),
        'width': int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0),
        'height': int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0),
        'fourcc': int(cap.get(cv2.CAP_PROP_FOURCC) or 0),
    }
    return props


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def compute_hotspot_mask(
    video_path: Path,
    red_thresh: int = 220,
    frac: float = 0.8,
    stride: int = 60,
    max_samples: int = 300,
    dilate: int = 1,
) -> np.ndarray:
    """Compute a boolean mask of persistent bright hotspots.

    Strategy:
    - Sample frames every `stride` up to `max_samples` frames.
    - For each sampled frame, mark pixels where R >= red_thresh.
    - After sampling, a pixel is considered a hotspot if it's above threshold
      in at least `frac` fraction of the sampled frames.
    - Optionally dilate the mask by `dilate` pixels to cover sensor bleed.
    """
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video for hotspot scan: {video_path}")

    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if frame_count <= 0:
        frame_count = 10**9  # unknown; iterate until read fails

    samples_taken = 0
    acc = None  # accumulator for counts

    idx = 0
    while samples_taken < max_samples and idx < frame_count:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret:
            break
        # BGR -> use red channel for hotspot detection
        red = frame[:, :, 2]
        hot = (red >= red_thresh)
        if acc is None:
            acc = hot.astype(np.uint16)
        else:
            acc += hot.astype(np.uint16)
        samples_taken += 1
        idx += stride

    cap.release()

    if acc is None or samples_taken == 0:
        raise RuntimeError("Failed to sample frames for hotspot detection.")

    # Persistent if present in >= frac of samples
    thresh_count = int(np.ceil(frac * samples_taken))
    mask = (acc >= thresh_count).astype(np.uint8) * 255

    if dilate > 0:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * dilate + 1, 2 * dilate + 1))
        mask = cv2.dilate(mask, k)

    return mask


def main() -> int:
    args = parse_args()
    video_path = args.video

    if not video_path.exists():
        print(f"Error: video not found: {video_path}", file=sys.stderr)
        return 2

    cap = open_capture(video_path)
    if not cap.isOpened():
        print(f"Error: cannot open video: {video_path}", file=sys.stderr)
        return 3

    props = get_props(cap)
    fps = props['fps'] if props['fps'] > 0 else 30.0
    if args.fps_limit and args.fps_limit > 0:
        fps = min(fps, args.fps_limit)
    target_dt = 1.0 / max(fps, 1e-3)

    print(f"Opened: {video_path}")
    print(f"Resolution: {props['width']}x{props['height']}  FPS: {props['fps']:.2f}  Frames: {props['frame_count']}")
    print(f"Playback target FPS: {fps:.2f}  frame_budget_ms: {int(target_dt*1000)}")

    # Optional: build hotspot mask (auto) before any display/IO heavy work
    hotspot_mask = None
    if args.mask_in is not None:
        try:
            m = cv2.imread(str(args.mask_in), cv2.IMREAD_GRAYSCALE)
            if m is None:
                raise RuntimeError("failed to read mask image")
            hotspot_mask = (m > 0).astype(np.uint8) * 255
            print(f"Loaded hotspot mask from {args.mask_in}  (nonzero={(hotspot_mask>0).sum()})")
        except Exception as e:
            print(f"Warning: failed to load mask from {args.mask_in}: {e}")
            hotspot_mask = None
    elif args.hotspots == 'auto':
        try:
            print("Detecting persistent hotspots (auto)...")
            hotspot_mask = compute_hotspot_mask(
                video_path,
                red_thresh=args.red_thresh,
                frac=args.frac,
                stride=args.stride,
                max_samples=args.max_samples,
                dilate=args.dilate,
            )
            nonzero = int((hotspot_mask > 0).sum())
            print(f"Hotspot mask computed: {nonzero} pixels flagged.")
            if args.mask_out is None:
                # default to data/processed/<video>_hotmask.png
                repo_root = Path(__file__).resolve().parents[1]
                out_dir = repo_root / 'data' / 'processed'
                ensure_parent_dir(out_dir / 'dummy')
                args.mask_out = out_dir / f"{video_path.stem}_hotmask.png"
            ensure_parent_dir(args.mask_out)
            cv2.imwrite(str(args.mask_out), hotspot_mask)
            print(f"Saved hotspot mask to {args.mask_out}")
        except Exception as e:
            print(f"Warning: hotspot detection failed: {e}")
            hotspot_mask = None

    # Dry run: read a frame and print stats without opening a window
    if args.dry_run:
        ret, frame = cap.read()
        if not ret:
            print("Error: failed to read first frame.", file=sys.stderr)
            cap.release()
            return 4
        if args.scale != 1.0:
            frame = cv2.resize(frame, None, fx=args.scale, fy=args.scale, interpolation=cv2.INTER_AREA)
        h, w = frame.shape[:2]
        print(f"First frame shape: {frame.shape} (HxW={h}x{w}) dtype={frame.dtype}")
        # extract channels (BGR)
        blue = frame[:, :, 0]
        green = frame[:, :, 1]
        red = frame[:, :, 2]
        print(
            "Channels stats -> "
            f"B: min={blue.min()}, max={blue.max()}, mean={float(blue.mean()):.2f}; "
            f"G: min={green.min()}, max={green.max()}, mean={float(green.mean()):.2f}; "
            f"R: min={red.min()}, max={red.max()}, mean={float(red.mean()):.2f}"
        )
        if hotspot_mask is not None:
            coverage = float((hotspot_mask > 0).sum()) / (h * w) * 100.0
            print(f"Hotspot mask coverage: {coverage:.4f}% of pixels")
        cap.release()
        return 0

    paused = False
    suffix = " + hotspots masked" if (hotspot_mask is not None and args.mask_mode != 'none') else ""
    win_name = f"B+G only (R=0){suffix}: {video_path.name}"
    cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)

    # Prepare a resized mask lazily when we know display size
    mask_to_apply = None

    while True:
        loop_start = time.perf_counter()
        if not paused:
            ret, frame = cap.read()
            if not ret:
                # reached end or read error
                break

            # frame is BGR; zero-out red channel to show only B+G
            disp = frame
            if args.scale != 1.0:
                disp = cv2.resize(disp, None, fx=args.scale, fy=args.scale, interpolation=cv2.INTER_AREA)
            disp = disp.copy()
            disp[:, :, 2] = 0

            # Apply hotspot mask if available: inpaint or black-out
            if hotspot_mask is not None and args.mask_mode != 'none':
                if mask_to_apply is None or mask_to_apply.shape[:2] != disp.shape[:2]:
                    mask_to_apply = cv2.resize(
                        hotspot_mask, (disp.shape[1], disp.shape[0]), interpolation=cv2.INTER_NEAREST
                    )
                mask8 = mask_to_apply if mask_to_apply.dtype == np.uint8 else mask_to_apply.astype(np.uint8)
                if args.mask_mode == 'inpaint':
                    try:
                        disp = cv2.inpaint(disp, mask8, max(1, int(args.inpaint_radius)), cv2.INPAINT_TELEA)
                        disp[:, :, 2] = 0  # ensure red remains zero after inpaint
                    except Exception:
                        # Fallback: black-out masked pixels
                        disp[mask8 > 0] = 0
                elif args.mask_mode == 'blackout':
                    disp[mask8 > 0] = 0

            cv2.imshow(win_name, disp)

        # Adjust wait time to maintain target FPS accounting for processing time
        elapsed = time.perf_counter() - loop_start
        remaining = max(target_dt - elapsed, 0.0)
        wait_ms = max(int(remaining * 1000), 1)
        key = cv2.waitKey(wait_ms) & 0xFF
        if key in (27, ord('q')):  # ESC or q
            break
        elif key == ord(' '):  # space to pause/resume
            paused = not paused

    cap.release()
    cv2.destroyAllWindows()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
