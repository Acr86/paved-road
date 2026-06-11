# andamio — single entrypoint. Every capability the README claims maps to a
# target here; if it is not runnable from this file, the README must call it
# a blueprint.
SHELL := bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

CLUSTER := andamio
CLI := uv run --project platform-cli platform

.PHONY: help doctor up down clean demo demo-clean preview test lint tf-validate \
        deploy-local catalog argocd-password grafana-password

help: ## list available targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-18s %s\n", $$1, $$2}'

doctor: ## check required tools and versions
	@for tool in docker k3d kubectl uv git; do \
	  if command -v $$tool >/dev/null 2>&1; then printf '  %-9s ok  (%s)\n' $$tool "$$($$tool version --short 2>/dev/null | head -n1 || $$tool --version 2>/dev/null | head -n1)"; \
	  else printf '  %-9s MISSING\n' $$tool; fi; \
	done
	@docker info >/dev/null 2>&1 && echo '  daemon    ok' || echo '  daemon    NOT RUNNING'

up: ## create the k3d cluster, install Argo CD and apply the root app
	bash scripts/bootstrap.sh

down: ## delete the k3d cluster (everything in it disappears)
	k3d cluster delete $(CLUSTER)

clean: down ## cluster teardown plus local build leftovers
	rm -rf dist

demo: ## the golden path end to end: scaffold -> test -> validate -> deploy -> curl
	bash scripts/demo.sh

demo-clean: ## remove the artifacts created by `make demo`
	-kubectl -n services delete deployment,service,ingress demo-ledger --ignore-not-found
	rm -rf services/demo-ledger deploy/kustomize/services/demo-ledger
	rm -f catalog/demo-ledger.yaml

preview: ## simulate a preview environment offline: make preview PR=123
	@test -n "$(PR)" || { echo 'usage: make preview PR=<number> [TTL=<seconds>]'; exit 2; }
	bash scripts/preview-sim.sh $(PR) $(or $(TTL),7200)

deploy-local: ## build + import + deploy one service: make deploy-local SERVICE=fx-rates
	@test -n "$(SERVICE)" || { echo 'usage: make deploy-local SERVICE=<name>'; exit 2; }
	bash scripts/deploy-local.sh $(SERVICE)

test: ## every test suite in the repository (CLI, services, aiops)
	uv run --project platform-cli pytest platform-cli/tests
	@for svc in services/*/; do \
	  echo "==> $$svc"; \
	  (cd "$$svc" && uv run --extra dev --project . pytest); \
	done
	@if [ -d aiops/ci-triage ]; then (cd aiops/ci-triage && uv run --extra dev --project . pytest); fi

lint: ## ruff over every Python tree + shellcheck over scripts (if installed)
	uv run --project platform-cli ruff check platform-cli aiops services
	uv run --project platform-cli ruff format --check platform-cli aiops services
	@if command -v shellcheck >/dev/null 2>&1; then shellcheck scripts/*.sh; else echo 'shellcheck not installed — skipped (CI runs it)'; fi

tf-validate: ## same Terraform gates CI runs: fmt + validate per cloud/env
	bash scripts/tf-validate.sh

catalog: ## validate the catalog and render the static portal page
	$(CLI) validate
	$(CLI) catalog render

argocd-password: ## initial admin password of the local Argo CD
	@kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d; echo

grafana-password: ## admin password of the local Grafana
	@kubectl -n observability get secret kube-prometheus-stack-grafana -o jsonpath='{.data.admin-password}' | base64 -d; echo
