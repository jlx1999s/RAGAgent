#!/usr/bin/env bash
set -euo pipefail

# Simple dev starter for backend (uvicorn) and frontend (Vite)
# Usage:
#   ./scripts/start-dev.sh
# Environment overrides:
#   BACKEND_PORT   (default: 8001)
#   FRONTEND_PORT  (default: 3000)
#   API_BASE_URL   (default: http://localhost:${BACKEND_PORT}/api/v1)

BACKEND_PORT="${BACKEND_PORT:-8001}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
API_BASE_URL="${API_BASE_URL:-http://localhost:${BACKEND_PORT}/api/v1}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

info() { echo "[start-dev] $*"; }
warn() { echo "[start-dev][WARN] $*"; }

check_port() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    if lsof -i tcp:"${port}" >/dev/null 2>&1; then
      warn "Port ${port} appears in use. Ensure no other dev server is running."
    fi
  fi
}

start_backend() {
  cd "${ROOT_DIR}/backend"
  if [[ -f ".venv/bin/activate" ]]; then
    # shellcheck disable=SC1091
    source ".venv/bin/activate"
    info "Activated Python venv: ${PWD}/.venv"
  else
    warn "No venv found; using system Python"
  fi
  check_port "${BACKEND_PORT}"
  info "Starting backend on http://localhost:${BACKEND_PORT}/ (uvicorn --reload)"
  python -m uvicorn app:app --host 0.0.0.0 --port "${BACKEND_PORT}" --reload &
  BACKEND_PID=$!
  info "Backend PID: ${BACKEND_PID}"
}

start_frontend() {
  cd "${ROOT_DIR}/frontend"
  if [[ -f ".env.local" ]]; then
    warn ".env.local detected; it may override VITE_API_BASE_URL"
  fi
  check_port "${FRONTEND_PORT}"
  export VITE_API_BASE_URL="${API_BASE_URL}"
  info "VITE_API_BASE_URL=${VITE_API_BASE_URL}"
  info "Starting frontend on http://localhost:${FRONTEND_PORT}/ (vite dev)"
  npm run dev -- --port "${FRONTEND_PORT}" &
  FRONTEND_PID=$!
  info "Frontend PID: ${FRONTEND_PID}"
}

cleanup() {
  echo ""; info "Stopping services..."
  # Try to terminate process groups to stop spawned children cleanly
  if [[ -n "${FRONTEND_PID:-}" ]]; then kill -TERM -"${FRONTEND_PID}" 2>/dev/null || kill "${FRONTEND_PID}" 2>/dev/null || true; fi
  if [[ -n "${BACKEND_PID:-}" ]]; then kill -TERM -"${BACKEND_PID}" 2>/dev/null || kill "${BACKEND_PID}" 2>/dev/null || true; fi
  wait "${FRONTEND_PID:-}" 2>/dev/null || true
  wait "${BACKEND_PID:-}" 2>/dev/null || true
  info "Stopped."
}

trap cleanup EXIT INT TERM

info "Repo root: ${ROOT_DIR}"
info "Backend port: ${BACKEND_PORT} | Frontend port: ${FRONTEND_PORT}"
info "API base: ${API_BASE_URL}"

start_backend
start_frontend

info "Frontend: http://localhost:${FRONTEND_PORT}/"
info "Backend:  http://localhost:${BACKEND_PORT}/"
info "Press Ctrl+C to stop both."

# Keep script attached to child processes; wait until one exits
wait