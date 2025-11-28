#!/usr/bin/env python3
"""
Convert PyroScience Workbench .txt files to simple CSV format.

This script converts the tab-delimited output from PyroScience Workbench 
into the simple CSV format expected by the R respirometry analysis script.

Output format: seconds,hours,clock,Ch1,Ch2,Ch3,Ch4,Temp
"""

import pandas as pd
import argparse
from pathlib import Path
import re


def find_data_start_line(filepath):
    """Find the line number where measurement data starts."""
    with open(filepath, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            # Data section starts after the metadata headers
            if line.startswith('Date [A Ch.1 Main]'):
                return i + 1  # Next line is data
    raise ValueError(f"Could not find data start line in {filepath}")


def parse_newbox_txt(filepath):
    """
    Parse PyroScience Workbench .txt file and extract key columns.
    
    Args:
        filepath: Path to the .txt file
    
    Returns:
        DataFrame with columns: seconds, hours, clock, Ch1, Ch2, Ch3, Ch4, Temp
    """
    # Find where data starts (skip all the metadata headers)
    data_start_line = find_data_start_line(filepath)
    
    # Read the tab-delimited file starting from data line
    df = pd.read_csv(filepath, sep='\t', skiprows=data_start_line, low_memory=False)
    
    # Extract relevant columns
    # Time in seconds: ' dt (s) [A Ch.1 Main]'
    # Oxygen for each channel: 'Oxygen (µmol/L) [A Ch.X Main]'
    # Temperature: 'Sample Temp. (°C) [A Ch.1 CompT]' (use Ch1's temp sensor)
    # Time: 'Time [A Ch.1 Main]'
    
    result = pd.DataFrame()
    
    # Seconds (using Ch1's dt column as reference)
    seconds_col = ' dt (s) [A Ch.1 Main]'
    if seconds_col in df.columns:
        result['seconds'] = df[seconds_col]
        result['hours'] = result['seconds'] / 3600.0
    else:
        raise ValueError(f"Could not find seconds column: {seconds_col}")
    
    # Clock time (using Ch1's time as reference)
    time_col = 'Time [A Ch.1 Main]'
    if time_col in df.columns:
        result['clock'] = df[time_col]
    else:
        raise ValueError(f"Could not find time column: {time_col}")
    
    # Oxygen channels (Ch1, Ch2, Ch3, Ch4)
    for ch_num in [1, 2, 3, 4]:
        oxygen_col = f'Oxygen (µmol/L) [A Ch.{ch_num} Main]'
        if oxygen_col in df.columns:
            result[f'Ch{ch_num}'] = df[oxygen_col]
        else:
            raise ValueError(f"Could not find oxygen column: {oxygen_col}")
    
    # Temperature (using Ch1's temperature compensation sensor)
    temp_col = 'Sample Temp. (°C) [A Ch.1 CompT]'
    if temp_col in df.columns:
        result['Temp'] = df[temp_col]
    else:
        raise ValueError(f"Could not find temperature column: {temp_col}")
    
    return result


def convert_newbox_file(input_path, output_path=None, output_dir=None):
    """
    Convert a single newbox .txt file to CSV format.
    
    Args:
        input_path: Path to input .txt file
        output_path: Path for output CSV (optional)
        output_dir: Directory for output CSV (optional, defaults to same as input)
    
    Returns:
        Path to output file
    """
    input_path = Path(input_path)
    
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    
    # Determine output path
    if output_path:
        output_path = Path(output_path)
    else:
        # Generate output filename from input
        # e.g., "2025-11-13_185203_Ostracods-trial4-newbox-13Nov.txt"
        # -> "Ostracods-trial4-newbox-13Nov.csv"
        
        # Try to extract a sensible name from the input filename
        stem = input_path.stem
        # Remove timestamp prefix if present
        match = re.search(r'(Ostracods-trial\d+(?:\.\d+)?-newbox-\d+\w+)', stem)
        if match:
            base_name = match.group(1)
        else:
            # Fallback to just removing timestamp-like prefixes
            base_name = re.sub(r'^\d{4}-\d{2}-\d{2}_\d{6}_', '', stem)
        
        if output_dir:
            output_path = Path(output_dir) / f"{base_name}.csv"
        else:
            # Use parent directory of input file
            output_path = input_path.parent / f"{base_name}.csv"
    
    print(f"Converting: {input_path}")
    print(f"Output to: {output_path}")
    
    # Parse and convert
    df = parse_newbox_txt(input_path)
    
    # Write to CSV
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    
    print(f"✓ Converted {len(df)} rows")
    print(f"  Time range: {df['hours'].min():.2f} - {df['hours'].max():.2f} hours")
    print(f"  Temp range: {df['Temp'].min():.2f} - {df['Temp'].max():.2f} °C")
    
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description='Convert PyroScience newbox .txt files to simple CSV format'
    )
    parser.add_argument(
        'input',
        type=str,
        help='Input .txt file path'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        help='Output CSV file path (optional)'
    )
    parser.add_argument(
        '-d', '--output-dir',
        type=str,
        help='Output directory (optional, uses input dir if not specified)'
    )
    
    args = parser.parse_args()
    
    try:
        output_file = convert_newbox_file(
            args.input,
            output_path=args.output,
            output_dir=args.output_dir
        )
        print(f"\n✓ Success! Output saved to: {output_file}")
        return 0
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit(main())
