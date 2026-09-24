.PHONY: help static format clean

help:
	@echo "Available targets:"
	@echo "  help   - show this text"
	@echo "  static - run static code analysis"
	@echo "  format - run auto code formatter"
	@echo "  clean  - clean cache and artifacts"

static:
	uv run ruff check src
	uv run ruff format --check src
	uv run ty check src

format:
	uv run ruff check --fix src
	uv run ruff format src

clean:
	rm -rf .venv .ruff_cache
