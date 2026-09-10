.PHONY: setup test lint fmt ingest check-upstream eda skeleton-sample skeleton annotate extract index train eval serve demo

NOT_IMPL = @echo "not implemented until its phase — see TODO.md" && exit 1
CASE ?=

setup:
	uv sync --group dev
	bash scripts/install-hooks.sh

test:
	uv run pytest

lint:
	uv run ruff check .

fmt:
	uv run ruff check --fix .

ingest:
	uv run python -m repeal.ingest.run

check-upstream:
	uv run python -m repeal.ingest.download --check-upstream

eda:
	uv run python -m repeal.ingest.profile --parquet data/interim/imr_cases.parquet --out docs/evals/eda.md

skeleton-sample:
	uv run python -m repeal.skeleton.cards --sample

skeleton:
	uv run python -m repeal.skeleton.run $(if $(CASE),--case $(CASE),)

annotate:
	$(NOT_IMPL)

extract:
	$(NOT_IMPL)

index:
	$(NOT_IMPL)

train:
	$(NOT_IMPL)

eval:
	$(NOT_IMPL)

serve:
	$(NOT_IMPL)

demo:
	$(NOT_IMPL)
