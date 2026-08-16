"""Project settings: filesystem layout and pinned seed.

Paths resolve from the repository root (derived from this file's location), so they
are stable regardless of the current working directory.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SEED = 42


@dataclass(frozen=True)
class Settings:
    project_root: Path
    data_dir: Path
    raw_dir: Path
    interim_dir: Path
    processed_dir: Path
    seed: int = SEED


def get_settings() -> Settings:
    """Build settings; `REPEAL_DATA_DIR` overrides the default `<project_root>/data`."""
    data_dir = Path(os.environ.get("REPEAL_DATA_DIR") or PROJECT_ROOT / "data").resolve()
    return Settings(
        project_root=PROJECT_ROOT,
        data_dir=data_dir,
        raw_dir=data_dir / "raw",
        interim_dir=data_dir / "interim",
        processed_dir=data_dir / "processed",
    )
