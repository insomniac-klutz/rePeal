"""Phase 0 smoke tests: package metadata, settings paths, and data-dir hygiene."""

from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path

import repeal
from repeal.config import get_settings

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_version_is_declared():
    assert repeal.__version__ == "0.1.0"


def test_version_matches_pyproject():
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    assert repeal.__version__ == pyproject["project"]["version"]


def test_main_is_callable():
    assert callable(repeal.main)


def test_data_dirs_derive_from_data_dir(monkeypatch):
    monkeypatch.delenv("REPEAL_DATA_DIR", raising=False)
    settings = get_settings()
    assert settings.data_dir.name == "data"
    assert settings.raw_dir == settings.data_dir / "raw"
    assert settings.interim_dir == settings.data_dir / "interim"
    assert settings.processed_dir == settings.data_dir / "processed"


def test_seed_is_pinned():
    assert get_settings().seed == 42


def test_paths_resolve_from_project_root_not_cwd(tmp_path, monkeypatch):
    monkeypatch.delenv("REPEAL_DATA_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    settings = get_settings()
    assert (settings.project_root / "PRD.md").is_file()
    assert settings.data_dir == settings.project_root / "data"


def test_data_dir_honours_env_override(tmp_path, monkeypatch):
    override = (tmp_path / "elsewhere").resolve()
    monkeypatch.setenv("REPEAL_DATA_DIR", str(override))
    settings = get_settings()
    assert settings.data_dir == override
    assert settings.raw_dir == override / "raw"


def test_data_dir_is_gitignored():
    result = subprocess.run(
        ["git", "check-ignore", "data/raw/_probe"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"data/ is not gitignored: {result.stderr}"
