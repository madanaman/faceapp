PYTHON_BIN ?= /opt/homebrew/Caskroom/miniforge/base/envs/faceapp/bin/python

.PHONY: run check

run:
	$(PYTHON_BIN) server.py

check:
	$(PYTHON_BIN) -m py_compile server.py backend/*.py
	node --check app.js
