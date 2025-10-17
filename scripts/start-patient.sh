#!/usr/bin/env bash
set -euo pipefail

# Patient-side dev starter for backend (uvicorn) and frontend (Vite)
# Usage:
#   ./scripts/start-patient.sh
# Environment overrides:
#   PATIENT_BACKEND_PORT   (default: 8001)
#   PATIENT_FRONTEND_PORT  (default: 3001)
#   PATIENT_API_BASE_URL   (default: http://localhost:${PATIENT_BACKEND_PORT}/api/v1)

PATIENT_BACKEND_PORT="${PATIENT_BACKEND_PORT:-8001}"
PATIENT_FRONTEND_PORT="${PATIENT_FRONTEND_PORT:-3001}"
PATIENT_API_BASE_URL="${PATIENT_API_BASE_URL:-http://localhost:${PATIENT_BACKEND_PORT}/api/v1}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

info() { echo "[start-patient] $*"; }
warn() { echo "[start-patient][WARN] $*"; }

check_port() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    if lsof -i tcp:"${port}" >/dev/null 2>&1; then
      warn "Port ${port} appears in use. Ensure no other dev server is running."
    fi
  fi
}

start_patient_backend() {
  cd "${ROOT_DIR}/backend/patient"
  if [[ -f "../../.venv/bin/activate" ]]; then
    # shellcheck disable=SC1091
    source "../../.venv/bin/activate"
    info "Activated Python venv: ${ROOT_DIR}/.venv"
  else
    warn "No venv found; using system Python"
  fi
  check_port "${PATIENT_BACKEND_PORT}"
  info "Starting patient backend on http://localhost:${PATIENT_BACKEND_PORT}/ (uvicorn --reload)"
  python -m uvicorn app:app --host 0.0.0.0 --port "${PATIENT_BACKEND_PORT}" --reload &
  PATIENT_BACKEND_PID=$!
  info "Patient backend PID: ${PATIENT_BACKEND_PID}"
}

start_patient_frontend() {
  cd "${ROOT_DIR}/frontend"
  
  # Copy patient environment file to .env.local for this session
  if [[ -f ".env.patient" ]]; then
    cp ".env.patient" ".env.local"
    info "Using patient environment configuration"
  else
    warn "No .env.patient found; creating one"
    echo "VITE_API_BASE_URL=${PATIENT_API_BASE_URL}" > ".env.local"
  fi
  
  check_port "${PATIENT_FRONTEND_PORT}"
  
  info "Starting patient frontend on http://localhost:${PATIENT_FRONTEND_PORT}/ (Vite dev server)"
  info "API base URL: ${PATIENT_API_BASE_URL}"
  npm run dev -- --port "${PATIENT_FRONTEND_PORT}" &
  PATIENT_FRONTEND_PID=$!
  info "Patient frontend PID: ${PATIENT_FRONTEND_PID}"
}

cleanup() {
  info "Shutting down patient services..."
  if [[ -n "${PATIENT_BACKEND_PID:-}" ]]; then
    kill "${PATIENT_BACKEND_PID}" 2>/dev/null || true
  fi
  if [[ -n "${PATIENT_FRONTEND_PID:-}" ]]; then
    kill "${PATIENT_FRONTEND_PID}" 2>/dev/null || true
  fi
  exit 0
}

trap cleanup SIGINT SIGTERM

info "Starting patient-side development environment..."
info "Backend port: ${PATIENT_BACKEND_PORT}"
info "Frontend port: ${PATIENT_FRONTEND_PORT}"
info "API base URL: ${PATIENT_API_BASE_URL}"

start_patient_backend
start_patient_frontend

info "Patient services started. Press Ctrl+C to stop."
wait