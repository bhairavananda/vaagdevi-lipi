PY := .venv/bin/python
# A Python new enough for uharfbuzz and pyobjc (macOS's own python3 is too old).
PYTHON ?= $(shell command -v python3.15 || command -v python3.14 || command -v python3.13 || command -v python3.12 || echo python3)

.PHONY: all font svara verify dev screenshots venv clean

all: font svara verify

venv:
	$(PYTHON) -m venv .venv && $(PY) -m pip install -q -r requirements.txt

font:
	$(PY) build.py
	$(PY) ligate.py

# The svara-coloured build: dist/VaagdeviSvara-Regular.ttf (see svara_color.py).
svara:
	$(PY) svara_color.py

verify:
	$(PY) verify.py
	$(PY) verify_iterm.py

# Install the current build into iTerm2 under a fresh name (see install_dev.py).
dev: font svara
	$(PY) install_dev.py

# Capture docs/images/rv-1.1-{without,vaagdevi,svara}.png from iTerm2 (see screenshots.py).
screenshots:
	python3 screenshots.py

clean:
	rm -rf dist
