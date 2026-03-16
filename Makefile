COMPOSE ?= docker compose

.PHONY: build up down logs test frontend-test frontend-build

build:
	$(COMPOSE) build

up:
	$(COMPOSE) up app

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f app

test:
	$(COMPOSE) run --rm app pytest

frontend-test:
	cd frontend && npm test

frontend-build:
	cd frontend && npm run build
