# Convenience targets. Every target is a thin wrapper — read it to see the real command.
SHELL := /bin/bash
CLUSTER ?= civicpulse
NS ?= civicpulse

.PHONY: help up down reset logs ps test test-backend test-frontend lint isolation persistence \
        k8s-up k8s-deploy k8s-down k8s-status load hpa-watch

help:          ## list targets
	@grep -E '^[a-z0-9-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

.env:
	cp .env.example .env
	@echo "Created .env from .env.example — change the passwords before sharing this machine."

up: .env       ## ONE COMMAND: build and start the whole stack with seeded data
	docker compose up -d --build --wait
	@echo; echo "CivicPulse is up:  http://localhost:$${FRONTEND_PORT:-8080}   (API docs: http://localhost:8000/docs)"

down:          ## stop the stack, KEEP data volumes
	docker compose down

reset:         ## stop the stack and DELETE data volumes
	docker compose down -v

logs:          ## follow backend logs (JSON)
	docker compose logs -f backend

ps:
	docker compose ps

test: test-backend test-frontend   ## run all tests (backend needs local Postgres + Redis, see README)

test-backend:
	cd backend && TRIAGE_PROVIDER=simulated python -m pytest --cov=app

test-frontend:
	cd frontend && npm test

lint:
	cd backend && ruff check . && ruff format --check . && mypy app
	cd frontend && npx eslint . && npx tsc --noEmit

isolation:     ## prove the frontend cannot reach the database (expected to FAIL to connect)
	./scripts/prove-isolation.sh

persistence:   ## prove rows survive `docker compose down` + `up`
	./scripts/prove-persistence.sh

k8s-up:        ## create a local k3d cluster and deploy the dev overlay
	./scripts/k8s-up.sh $(CLUSTER)

k8s-deploy:    ## re-apply the dev overlay to the existing cluster
	kubectl apply -k k8s/overlays/dev && kubectl -n $(NS) rollout status deploy/backend --timeout=180s

k8s-status:
	kubectl -n $(NS) get pods,svc,ingress,hpa,pdb,pvc

k8s-down:      ## delete the local cluster
	k3d cluster delete $(CLUSTER)

load:          ## k6 load test against the Ingress (BASE_URL=http://localhost:8081)
	k6 run -e BASE_URL=$${BASE_URL:-http://localhost:8081} load/k6-script.js

hpa-watch:     ## watch the HPA while `make load` runs in another terminal
	kubectl -n $(NS) get hpa backend -w
