"""Downloader for the DMHC IMR CSV: streaming fetch, manifest, drift probe, CLI.

Upstream is a single-file periodic republish behind a presigned-S3 redirect (HEAD 403s,
ranged GET works). `fetch()` pins one dated snapshot per OQ-1.3: idempotent on repeat
calls, explicit on refresh, and it adopts a raw file dropped in by hand instead of
re-downloading it. `probe()` and `check_upstream()` are the cheap, network-only-on-demand
drift guard from OQ-1.10 — never called from pytest or CI.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import requests

from repeal.config import get_settings

PACKAGE_ID = "independent-medical-review-imr-determinations-trend"
RESOURCE_ID = "3340c5d7-4054-4d03-90e0-5f44290ed095"
SOURCE_URL = (
    "https://data.chhs.ca.gov/dataset/b79b3447-4c10-4ae6-84e2-1076f83bb24e/resource/"
    "3340c5d7-4054-4d03-90e0-5f44290ed095/download/"
    "independent-medical-review-imr-determinations-trends.csv"
)
PACKAGE_SHOW_URL = "https://data.chhs.ca.gov/api/3/action/package_show"
DATASTORE_SEARCH_URL = "https://data.chhs.ca.gov/api/3/action/datastore_search"
EXPECTED_SOURCE_FIELDS: tuple[str, ...] = (
    "ReferenceID",
    "ReportYear",
    "DiagnosisCategory",
    "DiagnosisSubCategory",
    "TreatmentCategory",
    "TreatmentSubCategory",
    "Determination",
    "Type",
    "AgeRange",
    "PatientGender",
    "IMRType",
    "DaysToReview",
    "DaysToAdopt",
    "Findings",
)

_MANIFEST_FILENAME = "manifest.json"
_PART_FILENAME = ".imr_download.part"
_CHUNK_SIZE = 1 << 20  # 1 MiB
_REQUEST_TIMEOUT = 30
_DOWNLOAD_TIMEOUT = 60
_SNAPSHOT_RE = re.compile(r"^imr_(\d{4}-\d{2}-\d{2})(?:-(\d+))?\.csv$")
_CONTENT_RANGE_TOTAL_RE = re.compile(r"/(\d+)\s*$")


@dataclass(frozen=True)
class ManifestEntry:
    """One fetched/adopted snapshot of the source CSV, as recorded in manifest.json."""

    filename: str
    url: str
    resource_id: str
    upstream_last_modified: str | None
    retrieved_at: str
    sha256: str
    size_bytes: int


@dataclass
class Manifest:
    """manifest.json's contents: every known snapshot entry, plus which one is pinned."""

    pinned: str | None
    entries: list[ManifestEntry]


# --- manifest I/O ----------------------------------------------------------------------


def load_manifest(raw_dir: Path) -> Manifest | None:
    """Load manifest.json from `raw_dir`, or None if it doesn't exist yet."""
    path = raw_dir / _MANIFEST_FILENAME
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = [ManifestEntry(**item) for item in data.get("entries", [])]
    return Manifest(pinned=data.get("pinned"), entries=entries)


def save_manifest(raw_dir: Path, manifest: Manifest) -> None:
    """Write manifest.json atomically (temp file, then rename)."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "pinned": manifest.pinned,
        "entries": [asdict(entry) for entry in manifest.entries],
    }
    tmp_path = raw_dir / f".{_MANIFEST_FILENAME}.tmp"
    tmp_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(raw_dir / _MANIFEST_FILENAME)


def pinned(raw_dir: Path) -> ManifestEntry | None:
    """Return the currently pinned manifest entry, or None if there isn't one."""
    manifest = load_manifest(raw_dir)
    if manifest is None or manifest.pinned is None:
        return None
    return next((e for e in manifest.entries if e.filename == manifest.pinned), None)


# --- fetch -------------------------------------------------------------------------------


def fetch(
    raw_dir: Path,
    *,
    url: str = SOURCE_URL,
    refresh: bool = False,
    session: requests.Session | None = None,
    verify: bool = False,
) -> ManifestEntry:
    """Fetch (or reuse) the pinned IMR snapshot in `raw_dir`.

    A pinned entry whose file still exists is returned with zero HTTP calls unless
    `refresh=True` (OQ-1.3). With no manifest yet, a pre-existing `imr_*.csv` is adopted
    instead of downloaded. Otherwise the source CSV is streamed to a `.part` file while
    hashing, then atomically renamed to `imr_<upstream-last-modified-date>.csv`; a failed
    stream leaves neither the `.part` nor a final file behind.
    """
    raw_dir.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest(raw_dir)

    if not refresh and manifest is not None and manifest.pinned is not None:
        entry = next((e for e in manifest.entries if e.filename == manifest.pinned), None)
        if entry is not None:
            local_path = raw_dir / entry.filename
            if local_path.exists():
                _verify_local(local_path, entry, verify=verify)
                return entry

    if manifest is None:
        if not refresh:
            adopted = _adopt_existing(raw_dir, url=url)
            if adopted is not None:
                save_manifest(raw_dir, Manifest(pinned=adopted.filename, entries=[adopted]))
                return adopted
        manifest = Manifest(pinned=None, entries=[])

    if session is None:
        session = requests.Session()

    existing_filenames = _known_filenames(raw_dir, manifest)
    entry = _download_new(raw_dir, url, session, existing_filenames=existing_filenames)
    save_manifest(raw_dir, Manifest(pinned=entry.filename, entries=[*manifest.entries, entry]))
    return entry


def _verify_local(path: Path, entry: ManifestEntry, *, verify: bool) -> None:
    """Confirm a pinned file still matches its manifest entry.

    Size is a cheap stat, checked every time. A full sha256 costs a read of the whole
    file (85 MB), so it only runs when the caller asks for it.
    """
    actual_size = path.stat().st_size
    if actual_size != entry.size_bytes:
        raise ValueError(
            f"pinned file {path.name!r} is {actual_size} bytes, manifest says {entry.size_bytes}"
        )
    if verify:
        actual_sha256 = _sha256_of_file(path)
        if actual_sha256 != entry.sha256:
            raise ValueError(f"pinned file {path.name!r} sha256 does not match manifest")


def _adopt_existing(raw_dir: Path, *, url: str) -> ManifestEntry | None:
    """Adopt the newest unregistered `imr_*.csv` snapshot already sitting in `raw_dir`."""
    newest_path: Path | None = None
    newest_key: tuple[str, int] | None = None
    for path in sorted(raw_dir.glob("imr_*.csv")):
        match = _SNAPSHOT_RE.match(path.name)
        if match is None:
            continue
        date_str, suffix = match.group(1), match.group(2)
        key = (date_str, int(suffix) if suffix else 1)
        if newest_key is None or key > newest_key:
            newest_key, newest_path = key, path
    if newest_path is None or newest_key is None:
        return None
    return ManifestEntry(
        filename=newest_path.name,
        url=url,
        resource_id=RESOURCE_ID,
        upstream_last_modified=newest_key[0],
        retrieved_at=_iso_from_timestamp(newest_path.stat().st_mtime),
        sha256=_sha256_of_file(newest_path),
        size_bytes=newest_path.stat().st_size,
    )


def _download_new(
    raw_dir: Path,
    url: str,
    session: requests.Session,
    *,
    existing_filenames: set[str],
) -> ManifestEntry:
    upstream_last_modified = _fetch_upstream_last_modified(session)
    date_str = upstream_last_modified or _today_utc_str()
    part_path = raw_dir / _PART_FILENAME
    digest = hashlib.sha256()
    size = 0
    try:
        response = session.get(url, stream=True, allow_redirects=True, timeout=_DOWNLOAD_TIMEOUT)
        response.raise_for_status()
        with part_path.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=_CHUNK_SIZE):
                if not chunk:
                    continue
                handle.write(chunk)
                digest.update(chunk)
                size += len(chunk)
    except Exception:
        part_path.unlink(missing_ok=True)
        raise

    filename = _next_available_filename(date_str, existing_filenames)
    part_path.rename(raw_dir / filename)
    return ManifestEntry(
        filename=filename,
        url=url,
        resource_id=RESOURCE_ID,
        upstream_last_modified=upstream_last_modified,
        retrieved_at=_utc_now_iso(),
        sha256=digest.hexdigest(),
        size_bytes=size,
    )


def _fetch_upstream_last_modified(session: requests.Session) -> str | None:
    """The pinned resource's `last_modified` date per `package_show`, or None on failure."""
    try:
        response = session.get(
            PACKAGE_SHOW_URL, params={"id": PACKAGE_ID}, timeout=_REQUEST_TIMEOUT
        )
        response.raise_for_status()
        payload = response.json()
        for resource in payload["result"]["resources"]:
            if resource.get("id") == RESOURCE_ID:
                last_modified = resource.get("last_modified")
                return _date_only(last_modified) if last_modified else None
        return None
    except Exception:
        return None


def _date_only(value: str) -> str:
    return value.split("T")[0][:10]


def _known_filenames(raw_dir: Path, manifest: Manifest) -> set[str]:
    names = {path.name for path in raw_dir.glob("imr_*.csv")}
    names.update(entry.filename for entry in manifest.entries)
    return names


def _next_available_filename(date_str: str, existing: set[str]) -> str:
    candidate = f"imr_{date_str}.csv"
    if candidate not in existing:
        return candidate
    suffix = 2
    while True:
        candidate = f"imr_{date_str}-{suffix}.csv"
        if candidate not in existing:
            return candidate
        suffix += 1


def _sha256_of_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _iso_from_timestamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=UTC).isoformat()


def _today_utc_str() -> str:
    return datetime.now(UTC).date().isoformat()


# --- probe ---------------------------------------------------------------------------------


@dataclass
class ProbeResult:
    """What a ranged-GET probe against the source URL learned, without downloading it."""

    size_bytes: int | None
    last_modified: str | None


def probe(url: str = SOURCE_URL, session: requests.Session | None = None) -> ProbeResult:
    """Ranged GET (`Range: bytes=0-0`) for total size + Last-Modified; HEAD 403s on this host.

    Streamed and closed without reading the body: headers are all this needs, and if the
    host ever ignores the Range header and answers 200, a non-streamed read would pull the
    full ~85 MB into memory for nothing.
    """
    if session is None:
        session = requests.Session()
    response = session.get(
        url, headers={"Range": "bytes=0-0"}, timeout=_REQUEST_TIMEOUT, stream=True
    )
    try:
        response.raise_for_status()
        content_range = response.headers.get("Content-Range")
        size_bytes = None
        if content_range:
            match = _CONTENT_RANGE_TOTAL_RE.search(content_range)
            if match:
                size_bytes = int(match.group(1))
        return ProbeResult(
            size_bytes=size_bytes, last_modified=response.headers.get("Last-Modified")
        )
    finally:
        response.close()


# --- check_upstream --------------------------------------------------------------------------


@dataclass
class UpstreamReport:
    """Result of a datastore-API drift check against the currently pinned snapshot."""

    ok: bool
    expected_fields: tuple[str, ...]
    actual_fields: tuple[str, ...]
    missing: tuple[str, ...]
    extra: tuple[str, ...]
    row_count: int | None
    pinned_rows: int | None
    upstream_last_modified: str | None
    pinned_last_modified: str | None
    messages: list[str]


def check_upstream(
    raw_dir: Path,
    *,
    expected_fields: tuple[str, ...] = EXPECTED_SOURCE_FIELDS,
    session: requests.Session | None = None,
) -> UpstreamReport:
    """One-request-per-check drift probe: field contract, row count, republish date.

    Manual / pre-phase only (OQ-1.10) — never called from pytest or the commit-blocking
    CI job.
    """
    if session is None:
        session = requests.Session()

    actual_fields, row_count = _datastore_fields_and_count(session)
    upstream_last_modified = _fetch_upstream_last_modified(session)

    expected_set = set(expected_fields)
    actual_set = set(actual_fields)
    missing = tuple(f for f in expected_fields if f not in actual_set)
    extra = tuple(f for f in actual_fields if f not in expected_set)

    pinned_entry = pinned(raw_dir)
    pinned_last_modified = pinned_entry.upstream_last_modified if pinned_entry else None
    pinned_rows = _pinned_row_count(raw_dir)

    ok = True
    messages: list[str] = []

    if missing or extra:
        ok = False
        if missing:
            messages.append(f"missing fields: {', '.join(missing)}")
        if extra:
            messages.append(f"extra fields: {', '.join(extra)}")
    else:
        messages.append("field contract matches")

    if pinned_rows is not None and row_count is not None and row_count < pinned_rows:
        ok = False
        messages.append(f"upstream row_count {row_count} < pinned {pinned_rows}")

    if (
        upstream_last_modified is not None
        and pinned_last_modified is not None
        and upstream_last_modified > pinned_last_modified
    ):
        ok = False
        messages.append(
            f"upstream last_modified {upstream_last_modified} newer than "
            f"pinned {pinned_last_modified}"
        )

    return UpstreamReport(
        ok=ok,
        expected_fields=tuple(expected_fields),
        actual_fields=actual_fields,
        missing=missing,
        extra=extra,
        row_count=row_count,
        pinned_rows=pinned_rows,
        upstream_last_modified=upstream_last_modified,
        pinned_last_modified=pinned_last_modified,
        messages=messages,
    )


def _datastore_fields_and_count(session: requests.Session) -> tuple[tuple[str, ...], int | None]:
    response = session.get(
        DATASTORE_SEARCH_URL,
        params={"resource_id": RESOURCE_ID, "limit": 0},
        timeout=_REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    result = response.json()["result"]
    fields = tuple(f["id"] for f in result.get("fields", []) if f.get("id") != "_id")
    return fields, result.get("total")


def _pinned_row_count(raw_dir: Path) -> int | None:
    """The `"rows"` field of `data/interim/ingest_report.json`, if `run.py` has written one."""
    report_path = raw_dir.parent / "interim" / "ingest_report.json"
    if not report_path.exists():
        return None
    try:
        data = json.loads(report_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    value = data.get("rows")
    return value if isinstance(value, int) else None


# --- CLI -------------------------------------------------------------------------------------


def _print_probe(result: ProbeResult) -> None:
    print(f"size_bytes: {result.size_bytes}")
    print(f"last_modified: {result.last_modified}")


def _print_report(report: UpstreamReport) -> None:
    print(f"check-upstream: {'OK' if report.ok else 'DRIFT DETECTED'}")
    print(f"expected_fields ({len(report.expected_fields)}): {', '.join(report.expected_fields)}")
    print(f"actual_fields ({len(report.actual_fields)}): {', '.join(report.actual_fields)}")
    print(f"row_count: {report.row_count}  pinned_rows: {report.pinned_rows}")
    print(
        f"upstream_last_modified: {report.upstream_last_modified}  "
        f"pinned: {report.pinned_last_modified}"
    )
    for message in report.messages:
        print(f"- {message}")


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m repeal.ingest.download")
    parser.add_argument(
        "--probe", action="store_true", help="ranged-GET probe: size + Last-Modified"
    )
    parser.add_argument(
        "--check-upstream", action="store_true", help="datastore drift check vs the pinned entry"
    )
    parser.add_argument(
        "--refresh", action="store_true", help="force a fresh download to a new dated file"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    settings = get_settings()

    if args.probe:
        _print_probe(probe())
        return 0

    if args.check_upstream:
        report = check_upstream(settings.raw_dir)
        _print_report(report)
        return 0 if report.ok else 1

    entry = fetch(settings.raw_dir, refresh=args.refresh)
    print(f"pinned: {entry.filename} ({entry.size_bytes} bytes, sha256={entry.sha256})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
