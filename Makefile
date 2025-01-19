.PHONY: setup clean test format check build lock

POETRY := poetry

# Match with maximum set in pyproject.toml
# Use mise to make this easy in the parent env
# Example: mise use python@3.10 python@3.11 python@3.12
PYTHON_VERSION := python3.10
VENV_PATH := $(shell $(POETRY) env info -p 2>/dev/null)

.DEFAULT_GOAL := all

all: clean setup test build

# Clean build artifacts and virtual environment
clean:
	rm -rf dist/
	rm -rf build/
	rm -rf *.egg-info
	rm -rf .pytest_cache
	rm -rf .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +
	@if [ -d "$(VENV_PATH)" ]; then \
		echo "Removing existing virtual environment at $(VENV_PATH)"; \
		rm -rf $(VENV_PATH); \
	fi

# Set up Poetry environment with the specified Python version and install dependencies
setup: lock
	$(POETRY) env use $(PYTHON_VERSION)
	$(POETRY) install

# Build the project
build:
	$(POETRY) build

# Update lock file
lock:
	$(POETRY) lock

# Format code
format:
	$(POETRY) run black .
	$(POETRY) run isort .

# Run linting and type checks
check:
	$(POETRY) run flake8 .
	$(POETRY) run black --check .
	$(POETRY) run isort --check .

# Run tests (none for now)
#test:
#	$(POETRY) run pytest
