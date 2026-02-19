#!/usr/bin/env bash
set -euo pipefail

AWS_REGION="${AWS_REGION:-eu-west-1}"
CLUSTER_NAME="${CLUSTER_NAME:-forecast-prod-mongo-cluster}"
SERVICE_NAME="${SERVICE_NAME:-forecast-prod-mongo-mongo-1}"
CONTAINER_NAME="${CONTAINER_NAME:-mongodb}"
MONGO_ROOT_USERNAME="${MONGO_ROOT_USERNAME:-admin}"
APP_DB="${APP_DB:-forecast_2_0}"
APP_USER="${APP_USER:-}"
APP_PASS="${APP_PASS:-}"
BOOTSTRAP_SECRET_PREFIX="${BOOTSTRAP_SECRET_PREFIX:-forecast-prod-mongo-bootstrap}"
BOOTSTRAP_SECRET_ARN="${BOOTSTRAP_SECRET_ARN:-}"

if ! command -v aws >/dev/null 2>&1; then
  echo "aws CLI is required" >&2
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required" >&2
  exit 1
fi

if [[ -z "${APP_USER}" || -z "${APP_PASS}" ]]; then
  cat >&2 <<'USAGE'
Missing required variables.
Required:
  APP_USER
  APP_PASS
Optional:
  APP_DB (default: forecast_2_0)
  AWS_REGION (default: eu-west-1)
  CLUSTER_NAME (default: forecast-prod-mongo-cluster)
  SERVICE_NAME (default: forecast-prod-mongo-mongo-1)
  CONTAINER_NAME (default: mongodb)
  MONGO_ROOT_USERNAME (default: admin)
  BOOTSTRAP_SECRET_ARN (if unset, auto-detect latest by BOOTSTRAP_SECRET_PREFIX)
  BOOTSTRAP_SECRET_PREFIX (default: forecast-prod-mongo-bootstrap)
USAGE
  exit 1
fi

sq() {
  local s=${1//\'/\'"\'"\'}
  printf "'%s'" "$s"
}

if [[ -z "${BOOTSTRAP_SECRET_ARN}" ]]; then
  BOOTSTRAP_SECRET_ARN="$(aws secretsmanager list-secrets \
    --region "${AWS_REGION}" \
    --filters "Key=name,Values=${BOOTSTRAP_SECRET_PREFIX}" \
    --query 'sort_by(SecretList,&CreatedDate)[-1].ARN' \
    --output text) || true)"
fi

if [[ -z "${BOOTSTRAP_SECRET_ARN}" || "${BOOTSTRAP_SECRET_ARN}" == "None" ]]; then
  echo "Could not resolve bootstrap secret ARN" >&2
  exit 1
fi

ROOT_PASS="$(aws secretsmanager get-secret-value \
  --secret-id "${BOOTSTRAP_SECRET_ARN}" \
  --region "${AWS_REGION}" \
  --query SecretString \
  --output text | jq -r '.root_password')"

if [[ -z "${ROOT_PASS}" || "${ROOT_PASS}" == "null" ]]; then
  echo "root_password missing in secret ${BOOTSTRAP_SECRET_ARN}" >&2
  exit 1
fi

TASK_ARN="$(aws ecs list-tasks \
  --cluster "${CLUSTER_NAME}" \
  --service-name "${SERVICE_NAME}" \
  --desired-status RUNNING \
  --region "${AWS_REGION}" \
  --query 'taskArns[0]' \
  --output text)"

if [[ -z "${TASK_ARN}" || "${TASK_ARN}" == "None" ]]; then
  echo "No RUNNING task found for service ${SERVICE_NAME}" >&2
  exit 1
fi

remote_cmd=$(cat <<REMOTE
export APP_DB=$(sq "${APP_DB}")
export APP_USER=$(sq "${APP_USER}")
export APP_PASS=$(sq "${APP_PASS}")
export MONGO_ROOT_USERNAME=$(sq "${MONGO_ROOT_USERNAME}")
export MONGO_ROOT_PASSWORD=$(sq "${ROOT_PASS}")

mongosh --host 127.0.0.1 --port 27017 \
  -u "\$MONGO_ROOT_USERNAME" \
  -p "\$MONGO_ROOT_PASSWORD" \
  --authenticationDatabase admin \
  --eval 'const appDb=process.env.APP_DB||"forecast_2_0"; const appUser=process.env.APP_USER; const appPass=process.env.APP_PASS; const dbx=db.getSiblingDB(appDb); const roles=[{role:"readWrite",db:appDb}]; if(!dbx.getUser(appUser)){ dbx.createUser({user:appUser,pwd:appPass,roles}); print("created"); } else { dbx.updateUser(appUser,{pwd:appPass,roles}); print("updated"); }'
REMOTE
)

aws ecs execute-command \
  --cluster "${CLUSTER_NAME}" \
  --task "${TASK_ARN}" \
  --container "${CONTAINER_NAME}" \
  --interactive \
  --region "${AWS_REGION}" \
  --command "sh -lc $(sq "${remote_cmd}")"
