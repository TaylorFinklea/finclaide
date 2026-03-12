COMPOSE ?= docker compose

.PHONY: build up down logs test

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
