#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TF_DIR="${ROOT_DIR}/infra/terraform/mongodb-ecs"

if ! command -v terraform >/dev/null 2>&1; then
  echo "terraform is required" >&2
  exit 1
fi

TF_BACKEND_BUCKET="${TF_BACKEND_BUCKET:-}"
TF_BACKEND_KEY="${TF_BACKEND_KEY:-}"
TF_BACKEND_REGION="${TF_BACKEND_REGION:-eu-west-1}"
TF_BACKEND_DYNAMODB_TABLE="${TF_BACKEND_DYNAMODB_TABLE:-}"
TF_BACKEND_ENCRYPT="${TF_BACKEND_ENCRYPT:-true}"
TF_BACKEND_USE_LOCKFILE="${TF_BACKEND_USE_LOCKFILE:-true}"

if [[ -z "${TF_BACKEND_BUCKET}" || -z "${TF_BACKEND_KEY}" ]]; then
  cat >&2 <<'EOF'
Missing backend configuration.
Required environment variables:
  TF_BACKEND_BUCKET
  TF_BACKEND_KEY
Optional:
  TF_BACKEND_REGION (default: eu-west-1)
  TF_BACKEND_DYNAMODB_TABLE (legacy, optional)
  TF_BACKEND_ENCRYPT (default: true)
  TF_BACKEND_USE_LOCKFILE (default: true)
EOF
  exit 1
fi

INIT_ARGS=(
  "-input=false"
  "-backend-config=bucket=${TF_BACKEND_BUCKET}"
  "-backend-config=key=${TF_BACKEND_KEY}"
  "-backend-config=region=${TF_BACKEND_REGION}"
  "-backend-config=encrypt=${TF_BACKEND_ENCRYPT}"
  "-backend-config=use_lockfile=${TF_BACKEND_USE_LOCKFILE}"
)

if [[ -n "${TF_BACKEND_DYNAMODB_TABLE}" ]]; then
  INIT_ARGS+=("-backend-config=dynamodb_table=${TF_BACKEND_DYNAMODB_TABLE}")
fi

terraform -chdir="${TF_DIR}" init "${INIT_ARGS[@]}"
terraform -chdir="${TF_DIR}" plan -input=false
terraform -chdir="${TF_DIR}" apply -auto-approve -input=false
