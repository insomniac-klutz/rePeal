#!/usr/bin/env bash
set -euo pipefail

echo "installing git hooks via pre-commit..."
uv run pre-commit install
echo "done — ruff + pytest now run on every commit."
