.PHONY: setup test lint fmt ingest annotate extract index train eval serve demo

NOT_IMPL = @echo "not implemented until its phase — see TODO.md" && exit 1

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
	$(NOT_IMPL)

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
