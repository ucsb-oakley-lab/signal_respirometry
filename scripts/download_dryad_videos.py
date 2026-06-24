#!/usr/bin/env python3
"""Download the Photeros video files from their Dryad dataset by DOI."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


API_ROOT = "https://datadryad.org/api/v2"
USER_AGENT = "signal-respirometry-downloader/1.0"
GOPRO_FILENAMES = {
    "GX010063_2025Nov10.MP4",
    "GX010067_2025Nov12.MP4",
    "GX010072_2025Nov13.MP4",
    "GX01007X_2025Nov14.MP4",
}


def request(url: str) -> urllib.request.Request:
    return urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})


def fetch_json(url: str) -> dict:
    try:
        with urllib.request.urlopen(request(url)) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Dryad returned HTTP {error.code} for {url}: {detail}") from error


def link(document: dict, *names: str) -> str | None:
    links = document.get("_links", {})
    for name in names:
        value = links.get(name)
        if isinstance(value, dict) and value.get("href"):
            return value["href"]
    return None


def embedded(document: dict, *names: str) -> list[dict]:
    values = document.get("_embedded", {})
    for name in names:
        value = values.get(name)
        if isinstance(value, list):
            return value
    return []


def dryad_files(doi: str) -> list[dict]:
    dataset = fetch_json(f"{API_ROOT}/datasets/{urllib.parse.quote('doi:' + doi, safe='')}")
    if dataset.get("message"):
        raise RuntimeError(
            f"Dryad dataset {doi} is not publicly downloadable yet: {dataset['message']}"
        )
    version_url = link(dataset, "stash:version")
    if version_url:
        version = fetch_json(version_url)
    else:
        versions_url = link(dataset, "stash:versions")
        if not versions_url:
            raise RuntimeError("Dryad did not provide a dataset version link.")
        versions = fetch_json(versions_url)
        records = embedded(versions, "stash:versions", "versions")
        if not records:
            raise RuntimeError("Dryad returned no published dataset versions.")
        version = records[-1]
    files_url = link(version, "stash:files", "files")
    if files_url:
        listing = fetch_json(files_url)
        records = embedded(listing, "stash:files", "files")
    else:
        records = embedded(version, "stash:files", "files")
    if not records:
        raise RuntimeError("Dryad returned no downloadable files for this dataset version.")
    return records


def filename(record: dict) -> str:
    return Path(record.get("path") or record.get("name") or "").name


def download_url(record: dict) -> str:
    return link(record, "stash:download", "download") or f"{API_ROOT}/files/{record['id']}/download"


def sha256sum(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def advertised_sha256(record: dict) -> str | None:
    value = record.get("sha256")
    if isinstance(value, str):
        return value.removeprefix("sha256:").lower()
    for key in ("checksum", "digest"):
        value = record.get(key)
        if isinstance(value, str) and value.lower().startswith("sha256:"):
            return value.removeprefix("sha256:").lower()
    return None


def download(record: dict, output_dir: Path) -> None:
    name = filename(record)
    destination = output_dir / name
    expected = advertised_sha256(record)
    if destination.exists() and destination.stat().st_size:
        observed = sha256sum(destination)
        if not expected or observed == expected:
            print(f"Already present: {name}")
            return
        print(f"Replacing checksum-mismatched file: {name}")
    temporary = destination.with_suffix(destination.suffix + ".part")
    with urllib.request.urlopen(urllib.request.Request(download_url(record), headers={"User-Agent": USER_AGENT})) as response, temporary.open("wb") as handle:
        for chunk in iter(lambda: response.read(1024 * 1024), b""):
            handle.write(chunk)
    observed = sha256sum(temporary)
    if expected and observed != expected:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"Checksum mismatch for {name}: expected {expected}, got {observed}")
    temporary.replace(destination)
    print(f"Downloaded: {name} ({destination.stat().st_size} bytes; sha256={observed})")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--doi", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--include-arducam-zip", action="store_true")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    records = dryad_files(args.doi)
    selected = [record for record in records if filename(record) in GOPRO_FILENAMES]
    missing = GOPRO_FILENAMES - {filename(record) for record in selected}
    if missing:
        raise RuntimeError(f"Dryad dataset is published but missing expected GoPro files: {', '.join(sorted(missing))}")
    zip_files = [record for record in records if filename(record).lower().endswith('.zip')]
    if len(zip_files) != 1:
        print(f"Arducam ZIP candidates: {[filename(record) for record in zip_files]}")
    elif args.include_arducam_zip:
        selected.append(zip_files[0])
    else:
        print(f"Arducam ZIP available but not downloaded: {filename(zip_files[0])}")
    for record in sorted(selected, key=filename):
        download(record, args.output_dir)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
