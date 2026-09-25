.PHONY: help static format test clean

help:
	@echo "Available targets:"
	@echo "  help   - show this text"
	@echo "  static - run static code analysis"
	@echo "  format - run auto code formatter"
	@echo "  test   - run project tests"
	@echo "  clean  - clean cache and artifacts"

static:
	uv run ruff check src
	uv run ruff format --check src
	uv run ty check src

format:
	uv run ruff check --fix src
	uv run ruff format src

test:
	uv run pytest

clean:
	rm -rf .venv .ruff_cache .pytest_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
