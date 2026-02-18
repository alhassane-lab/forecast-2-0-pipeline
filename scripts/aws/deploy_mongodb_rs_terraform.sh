#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TF_DIR="${ROOT_DIR}/infra/terraform/mongodb-ecs"

if ! command -v terraform >/dev/null 2>&1; then
  echo "terraform is required" >&2
  exit 1
fi

terraform -chdir="${TF_DIR}" init
terraform -chdir="${TF_DIR}" plan
terraform -chdir="${TF_DIR}" apply -auto-approve
