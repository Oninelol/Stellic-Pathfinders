# Compass Planner — dev commands.
#   make setup    install dependencies + create the database
#   make run      start the API and the web server together
#   make test     run the test suite
#   make check    validate the nine catalog seeds
#   make seeds    regenerate data/*.json from scripts/curricula.py
#   make stop     stop both servers

PY  ?= python3
API_PORT ?= 8000
WEB_PORT ?= 8793

.PHONY: setup run api web test check seeds stop clean static

setup:
	$(PY) -m pip install -r requirements.txt
	$(PY) -m alembic upgrade head
	@echo "Ready. Run 'make run', then open http://localhost:$(WEB_PORT)/Compass%20Planner.html"

run: stop
	@nohup $(PY) -m uvicorn app.main:app --port $(API_PORT) --log-level warning > /tmp/compass-api.log 2>&1 & \
	 nohup $(PY) -m http.server $(WEB_PORT) > /dev/null 2>&1 & \
	 sleep 3; \
	 echo "API  -> http://localhost:$(API_PORT)/healthz"; \
	 echo "Docs -> http://localhost:$(API_PORT)/docs"; \
	 echo "App  -> http://localhost:$(WEB_PORT)/Compass%20Planner.html"

api:
	$(PY) -m uvicorn app.main:app --reload --port $(API_PORT)

web:
	$(PY) -m http.server $(WEB_PORT)

test:
	$(PY) -m pytest tests/ -q

check:
	$(PY) scripts/validate_catalog.py

seeds:
	$(PY) scripts/emit_seeds.py
	$(PY) scripts/validate_catalog.py

static:
	$(PY) scripts/build_static.py

stop:
	@pkill -f "uvicorn app.main" 2>/dev/null || true
	@pkill -f "http.server $(WEB_PORT)" 2>/dev/null || true
	@echo "servers stopped"

clean: stop
	rm -f compass.db
	@echo "database removed (run 'make setup' to recreate)"
