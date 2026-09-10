"""Tests for repeal.ingest.download: fetch, manifest, adoption, probe, check_upstream.

No network, ever — every HTTP call goes through FakeSession, which dispatches canned
FakeResponse objects by URL substring and records every call so tests can assert that
zero calls happened.
"""

from __future__ import annotations

import hashlib
import json

import pytest
import requests

from repeal.ingest import download as dl


class FakeResponse:
    """Stands in for `requests.Response`: status, headers, raise_for_status, iter_content, json."""

    def __init__(
        self,
        *,
        status_code=200,
        headers=None,
        content=b"",
        json_data=None,
        chunks=None,
        error_after_chunks=None,
    ):
        self.status_code = status_code
        self.headers = headers or {}
        self._content = content
        self._json_data = json_data
        self._chunks = chunks
        self._error_after_chunks = error_after_chunks
        self.iter_content_called = False
        self.closed = False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")

    def iter_content(self, chunk_size=1 << 20):
        # Not a generator itself: calling this must be observable even if the caller
        # never pulls from the returned iterator (that's the bug probe() had).
        self.iter_content_called = True
        return self._iter_content(chunk_size)

    def _iter_content(self, chunk_size):
        if self._chunks is not None:
            yield from self._chunks
            if self._error_after_chunks is not None:
                raise self._error_after_chunks
            return
        for i in range(0, len(self._content), chunk_size):
            yield self._content[i : i + chunk_size]

    def json(self):
        if self._json_data is None:
            raise ValueError("no json configured on this FakeResponse")
        return self._json_data

    def close(self):
        self.closed = True


class FakeSession:
    """Dispatches canned responses by URL substring; records every `.get()` call made."""

    def __init__(self, responses):
        self._responses = responses
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        for key, response in self._responses.items():
            if key in url:
                if isinstance(response, Exception):
                    raise response
                return response
        raise AssertionError(f"unexpected URL requested: {url}")


def _package_show_response(last_modified):
    return FakeResponse(
        json_data={
            "result": {
                "resources": [
                    {"id": dl.RESOURCE_ID, "last_modified": last_modified},
                ]
            }
        }
    )


def _download_session(content, *, last_modified="2026-06-01T00:00:00.000000"):
    return FakeSession(
        {
            dl.PACKAGE_SHOW_URL: _package_show_response(last_modified),
            dl.SOURCE_URL: FakeResponse(content=content),
        }
    )


CONTENT_V1 = b"ReferenceID,ReportYear\nMN26-1,2026\n" * 500
CONTENT_V2 = b"ReferenceID,ReportYear\nMN26-2,2026\n" * 700


# --- fetch: fresh download -------------------------------------------------------------


def test_fetch_downloads_writes_dated_file_and_manifest(tmp_path):
    session = _download_session(CONTENT_V1)

    entry = dl.fetch(tmp_path, session=session)

    assert entry.filename == "imr_2026-06-01.csv"
    assert entry.upstream_last_modified == "2026-06-01"
    assert entry.resource_id == dl.RESOURCE_ID
    assert entry.size_bytes == len(CONTENT_V1)
    assert entry.sha256 == hashlib.sha256(CONTENT_V1).hexdigest()

    written = tmp_path / entry.filename
    assert written.read_bytes() == CONTENT_V1
    assert not (tmp_path / ".imr_download.part").exists()

    manifest_data = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest_data["pinned"] == entry.filename
    assert len(manifest_data["entries"]) == 1
    assert manifest_data["entries"][0]["sha256"] == entry.sha256


def test_fetch_sends_streaming_get_with_redirects(tmp_path):
    session = _download_session(CONTENT_V1)

    dl.fetch(tmp_path, session=session)

    urls = [url for url, _ in session.calls]
    assert dl.SOURCE_URL in urls
    _, kwargs = next(c for c in session.calls if c[0] == dl.SOURCE_URL)
    assert kwargs["stream"] is True
    assert kwargs["allow_redirects"] is True


# --- fetch: idempotent second call -----------------------------------------------------


def test_second_fetch_is_idempotent_with_zero_http_calls(tmp_path):
    first_session = _download_session(CONTENT_V1)
    first_entry = dl.fetch(tmp_path, session=first_session)

    second_session = FakeSession({})
    second_entry = dl.fetch(tmp_path, session=second_session)

    assert second_entry == first_entry
    assert second_session.calls == []


# --- fetch: refresh ----------------------------------------------------------------------


def test_refresh_downloads_new_dated_file_and_moves_pin(tmp_path):
    first_session = _download_session(CONTENT_V1, last_modified="2026-06-01T00:00:00")
    first_entry = dl.fetch(tmp_path, session=first_session)

    second_session = _download_session(CONTENT_V2, last_modified="2026-07-15T00:00:00")
    second_entry = dl.fetch(tmp_path, refresh=True, session=second_session)

    assert second_entry.filename == "imr_2026-07-15.csv"
    assert second_entry.filename != first_entry.filename
    assert (tmp_path / first_entry.filename).exists()
    assert (tmp_path / second_entry.filename).read_bytes() == CONTENT_V2

    manifest_data = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest_data["pinned"] == second_entry.filename
    assert len(manifest_data["entries"]) == 2


def test_refresh_same_day_collision_gets_suffixed(tmp_path):
    first_session = _download_session(CONTENT_V1, last_modified="2026-06-01T00:00:00")
    first_entry = dl.fetch(tmp_path, session=first_session)

    second_session = _download_session(CONTENT_V2, last_modified="2026-06-01T00:00:00")
    second_entry = dl.fetch(tmp_path, refresh=True, session=second_session)

    assert first_entry.filename == "imr_2026-06-01.csv"
    assert second_entry.filename == "imr_2026-06-01-2.csv"


# --- fetch: adoption ---------------------------------------------------------------------


def test_adopts_pre_existing_raw_file_with_no_manifest(tmp_path):
    raw_file = tmp_path / "imr_2026-06-01.csv"
    raw_file.write_bytes(CONTENT_V1)
    session = FakeSession({})

    entry = dl.fetch(tmp_path, session=session)

    assert entry.filename == "imr_2026-06-01.csv"
    assert entry.upstream_last_modified == "2026-06-01"
    assert entry.sha256 == hashlib.sha256(CONTENT_V1).hexdigest()
    assert entry.size_bytes == len(CONTENT_V1)
    assert session.calls == []

    manifest_data = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest_data["pinned"] == entry.filename


def test_adopts_newest_when_multiple_unregistered_files_exist(tmp_path):
    (tmp_path / "imr_2026-01-01.csv").write_bytes(CONTENT_V1)
    (tmp_path / "imr_2026-06-01.csv").write_bytes(CONTENT_V2)
    session = FakeSession({})

    entry = dl.fetch(tmp_path, session=session)

    assert entry.filename == "imr_2026-06-01.csv"
    assert session.calls == []


# --- fetch: failure leaves no partial or final file --------------------------------------


def test_failed_stream_leaves_no_part_or_final_file(tmp_path):
    failing_response = FakeResponse(
        chunks=[b"partial-bytes"], error_after_chunks=ConnectionError("dropped")
    )
    session = FakeSession(
        {
            dl.PACKAGE_SHOW_URL: _package_show_response("2026-06-01T00:00:00"),
            dl.SOURCE_URL: failing_response,
        }
    )

    with pytest.raises(ConnectionError):
        dl.fetch(tmp_path, session=session)

    assert not (tmp_path / ".imr_download.part").exists()
    assert list(tmp_path.glob("imr_*.csv")) == []


def test_failed_download_http_status_leaves_no_files(tmp_path):
    session = FakeSession(
        {
            dl.PACKAGE_SHOW_URL: _package_show_response("2026-06-01T00:00:00"),
            dl.SOURCE_URL: FakeResponse(status_code=503),
        }
    )

    with pytest.raises(requests.HTTPError):
        dl.fetch(tmp_path, session=session)

    assert not (tmp_path / ".imr_download.part").exists()
    assert list(tmp_path.glob("imr_*.csv")) == []


# --- fetch: package_show failure falls back to today's date -------------------------------


def test_package_show_failure_falls_back_to_today(tmp_path, monkeypatch):
    monkeypatch.setattr(dl, "_today_utc_str", lambda: "2026-09-09")
    session = FakeSession(
        {
            dl.PACKAGE_SHOW_URL: ConnectionError("dns fail"),
            dl.SOURCE_URL: FakeResponse(content=CONTENT_V1),
        }
    )

    entry = dl.fetch(tmp_path, session=session)

    assert entry.filename == "imr_2026-09-09.csv"
    assert entry.upstream_last_modified is None


def test_package_show_bad_status_falls_back_to_today(tmp_path, monkeypatch):
    monkeypatch.setattr(dl, "_today_utc_str", lambda: "2026-09-09")
    session = FakeSession(
        {
            dl.PACKAGE_SHOW_URL: FakeResponse(status_code=500),
            dl.SOURCE_URL: FakeResponse(content=CONTENT_V1),
        }
    )

    entry = dl.fetch(tmp_path, session=session)

    assert entry.filename == "imr_2026-09-09.csv"
    assert entry.upstream_last_modified is None


# --- fetch: local integrity check ----------------------------------------------------------


def test_fetch_raises_when_pinned_file_size_no_longer_matches_manifest(tmp_path):
    session = _download_session(CONTENT_V1)
    entry = dl.fetch(tmp_path, session=session)
    (tmp_path / entry.filename).write_bytes(CONTENT_V1 + b"corrupted")

    with pytest.raises(ValueError):
        dl.fetch(tmp_path, session=FakeSession({}))


def test_fetch_verify_true_catches_sha_mismatch_with_same_size(tmp_path):
    session = _download_session(CONTENT_V1)
    entry = dl.fetch(tmp_path, session=session)
    tampered = CONTENT_V1[:-4] + b"XXXX"
    assert len(tampered) == len(CONTENT_V1)
    (tmp_path / entry.filename).write_bytes(tampered)

    with pytest.raises(ValueError):
        dl.fetch(tmp_path, session=FakeSession({}), verify=True)


# --- manifest helpers ----------------------------------------------------------------------


def test_load_manifest_returns_none_when_absent(tmp_path):
    assert dl.load_manifest(tmp_path) is None


def test_pinned_returns_none_with_no_manifest(tmp_path):
    assert dl.pinned(tmp_path) is None


def test_manifest_roundtrip(tmp_path):
    entry = dl.ManifestEntry(
        filename="imr_2026-06-01.csv",
        url=dl.SOURCE_URL,
        resource_id=dl.RESOURCE_ID,
        upstream_last_modified="2026-06-01",
        retrieved_at="2026-06-01T00:00:00+00:00",
        sha256="a" * 64,
        size_bytes=85409358,
    )
    dl.save_manifest(tmp_path, dl.Manifest(pinned=entry.filename, entries=[entry]))

    loaded = dl.load_manifest(tmp_path)

    assert loaded == dl.Manifest(pinned=entry.filename, entries=[entry])
    assert dl.pinned(tmp_path) == entry


# --- probe -----------------------------------------------------------------------------


def test_probe_parses_content_range_and_last_modified():
    response = FakeResponse(
        status_code=206,
        headers={
            "Content-Range": "bytes 0-0/85409358",
            "Last-Modified": "Mon, 01 Jun 2026 00:00:00 GMT",
        },
    )
    session = FakeSession({dl.SOURCE_URL: response})

    result = dl.probe(session=session)

    assert result.size_bytes == 85409358
    assert result.last_modified == "Mon, 01 Jun 2026 00:00:00 GMT"
    _, kwargs = session.calls[0]
    assert kwargs["headers"]["Range"] == "bytes=0-0"
    assert kwargs["stream"] is True
    assert response.closed is True


def test_probe_handles_missing_content_range_and_never_reads_the_body():
    # A host that ignores Range and answers 200 must not trigger a full-body read: a
    # non-streamed probe would otherwise pull the whole ~85 MB into memory for nothing.
    response = FakeResponse(status_code=200, headers={})
    session = FakeSession({dl.SOURCE_URL: response})

    result = dl.probe(session=session)

    assert result.size_bytes is None
    assert result.last_modified is None
    assert response.iter_content_called is False
    assert response.closed is True
    _, kwargs = session.calls[0]
    assert kwargs["stream"] is True


# --- check_upstream ----------------------------------------------------------------------


def _datastore_response(fields, total):
    return FakeResponse(
        json_data={
            "result": {
                "fields": [{"id": "_id"}] + [{"id": f} for f in fields],
                "total": total,
            }
        }
    )


def _check_session(fields, total, last_modified):
    return FakeSession(
        {
            dl.DATASTORE_SEARCH_URL: _datastore_response(fields, total),
            dl.PACKAGE_SHOW_URL: _package_show_response(last_modified),
        }
    )


def test_check_upstream_ok_when_fields_and_dates_match(tmp_path):
    raw_dir = tmp_path / "raw"
    session = _check_session(
        list(dl.EXPECTED_SOURCE_FIELDS), total=42749, last_modified="2026-06-01T00:00:00"
    )

    report = dl.check_upstream(raw_dir, session=session)

    assert report.ok
    assert report.missing == ()
    assert report.extra == ()
    assert report.row_count == 42749
    assert report.upstream_last_modified == "2026-06-01"


def test_check_upstream_flags_missing_and_extra_fields(tmp_path):
    raw_dir = tmp_path / "raw"
    fields = [f for f in dl.EXPECTED_SOURCE_FIELDS if f != "IMRType"] + ["SurpriseField"]
    session = _check_session(fields, total=42749, last_modified="2026-06-01T00:00:00")

    report = dl.check_upstream(raw_dir, session=session)

    assert not report.ok
    assert report.missing == ("IMRType",)
    assert report.extra == ("SurpriseField",)


def test_check_upstream_flags_newer_upstream_than_pinned(tmp_path):
    raw_dir = tmp_path / "raw"
    dl.save_manifest(
        raw_dir,
        dl.Manifest(
            pinned="imr_2026-06-01.csv",
            entries=[
                dl.ManifestEntry(
                    filename="imr_2026-06-01.csv",
                    url=dl.SOURCE_URL,
                    resource_id=dl.RESOURCE_ID,
                    upstream_last_modified="2026-06-01",
                    retrieved_at="2026-06-01T00:00:00+00:00",
                    sha256="a" * 64,
                    size_bytes=85409358,
                )
            ],
        ),
    )
    session = _check_session(
        list(dl.EXPECTED_SOURCE_FIELDS), total=42900, last_modified="2026-07-15T00:00:00"
    )

    report = dl.check_upstream(raw_dir, session=session)

    assert not report.ok
    assert report.upstream_last_modified == "2026-07-15"
    assert report.pinned_last_modified == "2026-06-01"


def test_check_upstream_flags_row_count_below_pinned(tmp_path):
    raw_dir = tmp_path / "raw"
    interim_dir = tmp_path / "interim"
    interim_dir.mkdir()
    (interim_dir / "ingest_report.json").write_text(json.dumps({"rows": 42749}))
    session = _check_session(
        list(dl.EXPECTED_SOURCE_FIELDS), total=100, last_modified="2026-06-01T00:00:00"
    )

    report = dl.check_upstream(raw_dir, session=session)

    assert not report.ok
    assert report.pinned_rows == 42749
    assert report.row_count == 100


def test_check_upstream_skips_row_count_check_without_ingest_report(tmp_path):
    raw_dir = tmp_path / "raw"
    session = _check_session(
        list(dl.EXPECTED_SOURCE_FIELDS), total=42749, last_modified="2026-06-01T00:00:00"
    )

    report = dl.check_upstream(raw_dir, session=session)

    assert report.pinned_rows is None
    assert report.ok


# --- CLI -----------------------------------------------------------------------------------


def test_main_probe_dispatches_and_prints(monkeypatch, capsys):
    monkeypatch.setattr(dl, "probe", lambda: dl.ProbeResult(size_bytes=123, last_modified="x"))

    exit_code = dl.main(["--probe"])

    assert exit_code == 0
    assert "123" in capsys.readouterr().out


def test_main_check_upstream_ok_exits_zero(monkeypatch, tmp_path):
    monkeypatch.setattr(dl, "get_settings", lambda: _FakeSettings(tmp_path))
    ok_report = dl.UpstreamReport(
        ok=True,
        expected_fields=dl.EXPECTED_SOURCE_FIELDS,
        actual_fields=dl.EXPECTED_SOURCE_FIELDS,
        missing=(),
        extra=(),
        row_count=42749,
        pinned_rows=None,
        upstream_last_modified="2026-06-01",
        pinned_last_modified=None,
        messages=["field contract matches"],
    )
    monkeypatch.setattr(dl, "check_upstream", lambda raw_dir, **kw: ok_report)

    assert dl.main(["--check-upstream"]) == 0


def test_main_check_upstream_not_ok_exits_one(monkeypatch, tmp_path):
    monkeypatch.setattr(dl, "get_settings", lambda: _FakeSettings(tmp_path))
    bad_report = dl.UpstreamReport(
        ok=False,
        expected_fields=dl.EXPECTED_SOURCE_FIELDS,
        actual_fields=(),
        missing=dl.EXPECTED_SOURCE_FIELDS,
        extra=(),
        row_count=None,
        pinned_rows=None,
        upstream_last_modified=None,
        pinned_last_modified=None,
        messages=["missing fields: everything"],
    )
    monkeypatch.setattr(dl, "check_upstream", lambda raw_dir, **kw: bad_report)

    assert dl.main(["--check-upstream"]) == 1


def test_main_default_calls_fetch_with_refresh_flag(monkeypatch, tmp_path):
    monkeypatch.setattr(dl, "get_settings", lambda: _FakeSettings(tmp_path))
    captured = {}

    def fake_fetch(raw_dir, *, refresh=False):
        captured["raw_dir"] = raw_dir
        captured["refresh"] = refresh
        return dl.ManifestEntry(
            filename="imr_2026-06-01.csv",
            url=dl.SOURCE_URL,
            resource_id=dl.RESOURCE_ID,
            upstream_last_modified="2026-06-01",
            retrieved_at="2026-06-01T00:00:00+00:00",
            sha256="a" * 64,
            size_bytes=1,
        )

    monkeypatch.setattr(dl, "fetch", fake_fetch)

    assert dl.main(["--refresh"]) == 0
    assert captured == {"raw_dir": tmp_path, "refresh": True}


class _FakeSettings:
    def __init__(self, raw_dir):
        self.raw_dir = raw_dir
