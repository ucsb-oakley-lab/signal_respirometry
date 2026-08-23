#!/usr/bin/env python3
"""
Convert older PyroScience/FireSting-style .txt exports to simple CSV format.

This script is for old software exports (e.g., box2/box3 NOL files), which use
column headers like:
Date, Time (HH:MM:SS), Time (s), Ch1..Ch4, etc.

Output format: seconds,hours,clock,Ch1,Ch2,Ch3,Ch4,Temp
"""

import argparse
from io import StringIO
from pathlib import Path
import re

import pandas as pd


def detect_encoding(filepath):
    """Handle both UTF-8 exports and cp1252-encoded instrument files."""
    encodings = ['utf-8-sig', 'utf-8', 'cp1252']
    raw = Path(filepath).read_bytes()
    for enc in encodings:
        try:
            raw.decode(enc)
            return enc
        except UnicodeDecodeError:
            continue
    return 'cp1252'


def find_data_start_line(filepath):
    """Find the header row containing the oldbox measurement columns."""
    encoding = detect_encoding(filepath)
    with open(filepath, 'r', encoding=encoding, errors='replace') as f:
        for i, line in enumerate(f):
            stripped = line.strip()
            if not stripped:
                continue
            columns = [cell.strip() for cell in line.split('\t') if cell.strip()]
            col_text = '\t'.join(columns)
            if (
                'Date' in columns
                and 'Time (HH:MM:SS)' in col_text
                and 'Time (s)' in col_text
                and ('Ch1' in col_text or 'Ch 1' in col_text)
                and ('Ch2' in col_text or 'Ch 2' in col_text)
                and ('Ch3' in col_text or 'Ch 3' in col_text)
                and ('Ch4' in col_text or 'Ch 4' in col_text)
            ):
                return i
    raise ValueError(f"Could not find oldbox data start line in {filepath}")


def parse_oldbox_txt(filepath):
    """
    Parse oldbox PyroScience/FireSting-style .txt export.

    Returns a DataFrame with columns:
    seconds, hours, clock, Ch1, Ch2, Ch3, Ch4, Temp
    """
    encoding = detect_encoding(filepath)
    data_line = find_data_start_line(filepath)

    with open(filepath, 'r', encoding=encoding, errors='replace') as f:
        lines = [line.rstrip('\n') for line in f]

    header_block = '\n'.join(lines[data_line:])
    df = pd.read_csv(StringIO(header_block), sep='\t', header=0, engine='python', dtype=str)

    def choose_column(candidates):
        normalized = {str(col).strip(): col for col in df.columns}
        normalized_keyless = {
            re.sub(r'[^a-z0-9]+', '', str(col).strip().lower()): col
            for col in df.columns
        }
        for candidate in candidates:
            cand = str(candidate).strip()
            if cand in normalized:
                return normalized[cand]
            key = re.sub(r'[^a-z0-9]+', '', cand.lower())
            if key in normalized_keyless:
                return normalized_keyless[key]
            for col_name in df.columns:
                col_key = re.sub(r'[^a-z0-9]+', '', str(col_name).strip().lower())
                if key in col_key:
                    return col_name
        return None

    result = pd.DataFrame()

    seconds_col = choose_column(['Time (s)', ' dt (s) [A Ch.1 Main]', 'Time [A Ch.1 Main]'])
    if seconds_col is None:
        raise ValueError('Could not find seconds column in oldbox export')
    result['seconds'] = pd.to_numeric(df[seconds_col], errors='coerce')
    result['hours'] = result['seconds'] / 3600.0

    time_col = choose_column(['Time (HH:MM:SS)', 'Time [A Ch.1 Main]'])
    if time_col is None:
        raise ValueError('Could not find time column in oldbox export')
    result['clock'] = df[time_col].astype(str)

    for ch_num in [1, 2, 3, 4]:
        oxygen_col = choose_column([
            f'Ch{ch_num}',
            f'Ch {ch_num}',
            f'Oxygen (µmol/L) [A Ch.{ch_num} Main]',
        ])
        if oxygen_col is None:
            raise ValueError(f"Could not find oxygen column for Ch{ch_num}")
        result[f'Ch{ch_num}'] = pd.to_numeric(df[oxygen_col], errors='coerce')

    temp_candidates = [
        "('C)",
        'Temp. Probe',
        'Temperature',
        'Temp',
        'Sample Temp. (°C)',
        'Temp. (°C)',
        'Sample Temp. (°C) [A Ch.1 CompT]',
    ]
    temp_col = choose_column(temp_candidates)
    if temp_col is None:
        for col in df.columns:
            c = str(col).strip().lower().replace('°', '').replace('c)', 'c')
            if ('temp' in c or c.startswith("'c") or c.startswith('c')) and c not in {'ch 1', 'ch 2', 'ch 3', 'ch 4'}:
                temp_col = col
                break

    if temp_col is None:
        raise ValueError('Could not find temperature column in oldbox export')
    result['Temp'] = pd.to_numeric(df[temp_col], errors='coerce')

    return result


def convert_oldbox_file(input_path, output_path=None, output_dir=None):
    """Convert one oldbox .txt file to standardized CSV."""
    input_path = Path(input_path)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    if output_path:
        output_path = Path(output_path)
    else:
        if output_dir:
            output_path = Path(output_dir) / f"{input_path.stem}.csv"
        else:
            output_path = input_path.with_suffix('.csv')

    print(f"Converting oldbox file: {input_path}")
    print(f"Output to: {output_path}")

    df = parse_oldbox_txt(input_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)

    print(f"Converted {len(df)} rows")
    print(f"  Time range: {df['hours'].min():.2f} - {df['hours'].max():.2f} hours")
    print(f"  Temp range: {df['Temp'].min():.2f} - {df['Temp'].max():.2f} C")

    return output_path


def main():
    parser = argparse.ArgumentParser(
        description='Convert oldbox PyroScience/FireSting .txt files to simple CSV format'
    )
    parser.add_argument('input', type=str, help='Input .txt file path')
    parser.add_argument('-o', '--output', type=str, help='Output CSV file path (optional)')
    parser.add_argument('-d', '--output-dir', type=str, help='Output directory (optional)')

    args = parser.parse_args()

    try:
        output_file = convert_oldbox_file(
            args.input,
            output_path=args.output,
            output_dir=args.output_dir,
        )
        print(f"\nSuccess! Output saved to: {output_file}")
        return 0
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
