PY := .venv/bin/python
# A Python new enough for uharfbuzz and pyobjc (macOS's own python3 is too old).
PYTHON ?= $(shell command -v python3.15 || command -v python3.14 || command -v python3.13 || command -v python3.12 || echo python3)

.PHONY: all font verify dev venv clean

all: font verify

venv:
	$(PYTHON) -m venv .venv && $(PY) -m pip install -q -r requirements.txt

font:
	$(PY) build.py
	$(PY) ligate.py

verify:
	$(PY) verify.py
	$(PY) verify_iterm.py

# Install the current build into iTerm2 under a fresh name (see install_dev.py).
dev: font
	$(PY) install_dev.py

clean:
	rm -rf dist
