#!/usr/bin/env python3
import re
import sys
import argparse
from pathlib import Path
import csv

HEADER_MARKER_TOKENS = ["Date", "Time", "Time", "(s)", "Ch1", "Ch2", "Ch3", "Ch4"]

num_re = re.compile(r"[-+]?\d*\.\d+|[-+]?\d+")
time_re = re.compile(r"\b\d{2}:\d{2}:\d{2}\b")


def find_data_start(lines):
    """Return index of header line (0-based) where data columns begin.
    Looks for presence of key tokens typical to FireSting exports.
    """
    for i, line in enumerate(lines):
        if all(tok in line for tok in ["Date", "Time (s)", "Ch1", "Ch2", "Ch3", "Ch4"]):
            return i
    # Fallback: look for first line that contains 'Time (s)'
    for i, line in enumerate(lines):
        if "Time (s)" in line:
            return i
    return None


essential_count = 9  # secs + 4 O2 + 4 temp


def parse_firesting_lines(lines):
    """Parse FireSting text lines into rows with seconds, hours, clock, Ch1-4, Temp.

    Strategy: after the header line, extract all numeric tokens per line and
    take positions: [0]=seconds, [1]=Ch1, [2]=Ch2, [3]=Ch3, [4]=Ch4, [5]=Temp (first temp column).
    Skip rows that don't meet minimal numeric token count.
    """
    start_idx = find_data_start(lines)
    if start_idx is None:
        raise ValueError("Could not locate data header with 'Time (s)' and Ch1-4 in FireSting file.")
    data_rows = []
    for raw in lines[start_idx+1:]:
        if not raw.strip():
            continue
        m = time_re.search(raw)
        if not m:
            # skip lines without HH:MM:SS (likely non-data)
            continue
        time_str = m.group(0)
        tail = raw[m.end():]
        nums = num_re.findall(tail)
        if len(nums) < 6:
            # need at least seconds + 4 channels + temp
            continue
        try:
            seconds = float(nums[0])
            ch1 = float(nums[1]); ch2 = float(nums[2]); ch3 = float(nums[3]); ch4 = float(nums[4])
            temp = float(nums[5])  # first temperature column after channels
        except ValueError:
            continue
        hours = seconds / 3600.0
        data_rows.append((seconds, hours, time_str, ch1, ch2, ch3, ch4, temp))
    if not data_rows:
        raise ValueError("No data rows parsed from FireSting file; format may be unsupported.")
    return data_rows


def convert_file(in_path: Path, out_path: Path, overwrite: bool = False):
    text = in_path.read_text(errors='ignore')
    lines = text.splitlines()
    rows = parse_firesting_lines(lines)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists() and not overwrite:
        raise FileExistsError(f"Output exists: {out_path}. Use --overwrite to replace.")
    with out_path.open('w', newline='') as f:
        w = csv.writer(f)
        # Include clock time from the instrument for provenance
        w.writerow(["seconds","hours","clock","Ch1","Ch2","Ch3","Ch4","Temp"])
        for seconds, hours, clock, ch1, ch2, ch3, ch4, temp in rows:
            # Format hours to 9 decimals to match existing CSVs (e.g., 2.21/3600 => 0.000613889)
            hours_str = f"{hours:.9f}"
            w.writerow([seconds, hours_str, clock, ch1, ch2, ch3, ch4, temp])


def batch_convert(in_dir: Path, out_dir: Path, overwrite: bool = False):
    txts = sorted(in_dir.glob('*.txt'))
    if not txts:
        print(f"No .txt files found in {in_dir}")
        return
    for txt in txts:
        out_name = txt.stem
        # Map common FireSting names to desired CSV names if needed; by default keep stem
        out_csv = out_dir / f"{out_name}.csv"
        if out_csv.exists() and not overwrite:
            print(f"Skip existing {out_csv.name} (use --overwrite to regenerate)")
            continue
        try:
            convert_file(txt, out_csv, overwrite=overwrite)
            print(f"Converted {txt.name} -> {out_csv.name}")
        except Exception as e:
            print(f"Failed {txt.name}: {e}")


def main(argv=None):
    p = argparse.ArgumentParser(description="Convert FireStingO2 text export to standardized CSV")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument('--in', dest='infile', type=Path, help='Input .txt file path')
    g.add_argument('--in-dir', dest='indir', type=Path, help='Input directory containing .txt files')
    p.add_argument('--out', dest='outfile', type=Path, help='Output .csv file path (single-file mode)')
    p.add_argument('--out-dir', dest='outdir', type=Path, help='Output directory (batch mode)', default=None)
    p.add_argument('--overwrite', action='store_true', help='Overwrite existing outputs')
    args = p.parse_args(argv)

    if args.infile is not None:
        if args.outfile is None:
            raise SystemExit("--out is required when using --in")
        convert_file(args.infile, args.outfile, overwrite=args.overwrite)
        return

    # Batch mode
    outdir = args.outdir or args.indir
    outdir.mkdir(parents=True, exist_ok=True)
    batch_convert(args.indir, outdir, overwrite=args.overwrite)


if __name__ == '__main__':
    main()
