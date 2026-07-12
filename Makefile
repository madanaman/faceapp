PYTHON_BIN ?= python3

.PHONY: run check desktop-assets desktop-backend desktop-dev desktop-build

run:
	$(PYTHON_BIN) server.py

check:
	$(PYTHON_BIN) scripts/check.py

desktop-assets:
	mkdir -p desktop
	cp index.html styles.css app.js desktop/

desktop-backend:
	$(PYTHON_BIN) scripts/desktop_build.py

desktop-dev: desktop-assets
	npm run desktop:dev

desktop-build:
	$(PYTHON_BIN) scripts/desktop_build.py
