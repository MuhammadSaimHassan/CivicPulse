#!/usr/bin/env bash
# One command to a running Kubernetes deployment on your laptop:
#   make k8s-up        (or: ./scripts/k8s-up.sh [cluster-name])
#
# Creates a k3d cluster (k3s in Docker: ships Traefik for the Ingress and
# metrics-server for the HPA), installs the Vertical Pod Autoscaler, builds and
# imports the two images, writes the dev Secret from your .env, and applies
# k8s/overlays/dev. Requires: docker, k3d (>= 5.9), kubectl, git, openssl.
set -euo pipefail
CLUSTER="${1:-civicpulse}"
NS=civicpulse
VPA_VERSION="vertical-pod-autoscaler-1.8.0"
cd "$(dirname "$0")/.."

for bin in docker k3d kubectl; do command -v "$bin" >/dev/null || { echo "missing: $bin"; exit 1; }; done
[ -f .env ] || cp .env.example .env

if ! k3d cluster list "$CLUSTER" >/dev/null 2>&1; then
  # Host port 8081 -> the cluster's Traefik Ingress on port 80.
  k3d cluster create "$CLUSTER" --agents 2 -p "8081:80@loadbalancer" --wait
fi
kubectl config use-context "k3d-$CLUSTER" >/dev/null

if ! kubectl get crd verticalpodautoscalers.autoscaling.k8s.io >/dev/null 2>&1; then
  echo "== installing VPA ($VPA_VERSION): recommender, updater, admission controller"
  tmp=$(mktemp -d)
  git clone --quiet --depth 1 --branch "$VPA_VERSION" https://github.com/kubernetes/autoscaler.git "$tmp/autoscaler"
  (cd "$tmp/autoscaler/vertical-pod-autoscaler" && ./hack/vpa-up.sh)
  rm -rf "$tmp"
fi

echo "== building images (tag :dev) and importing them into the cluster"
docker build -t civicpulse-backend:dev backend
docker build -t civicpulse-frontend:dev frontend
k3d image import -c "$CLUSTER" civicpulse-backend:dev civicpulse-frontend:dev

echo "== writing k8s/overlays/dev/secrets.env from .env (gitignored)"
get() { grep -E "^$1=" .env | tail -1 | cut -d= -f2-; }
umask 077
{
  echo "POSTGRES_PASSWORD=$(get POSTGRES_PASSWORD)"
  echo "REDIS_PASSWORD=$(get REDIS_PASSWORD)"
  echo "LLM_API_KEY=$(get LLM_API_KEY)"
} > k8s/overlays/dev/secrets.env

kubectl apply -k k8s/overlays/dev
kubectl -n "$NS" rollout status statefulset/postgres --timeout=180s
kubectl -n "$NS" rollout status deployment/redis --timeout=120s
kubectl -n "$NS" rollout status deployment/backend --timeout=240s
kubectl -n "$NS" rollout status deployment/frontend --timeout=120s
kubectl -n "$NS" get pods,svc,ingress,hpa
echo
echo "CivicPulse on Kubernetes: http://civicpulse.localhost:8081"
echo "(*.localhost resolves to 127.0.0.1 in most browsers; with curl use -H 'Host: civicpulse.localhost' http://127.0.0.1:8081)"
