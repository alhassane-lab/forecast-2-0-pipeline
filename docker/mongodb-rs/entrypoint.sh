#!/usr/bin/env bash
set -euo pipefail

MONGO_PORT="${MONGO_PORT:-27017}"
MONGO_DBPATH="${MONGO_DBPATH:-/data/db}"
MONGO_RS_NAME="${MONGO_REPLICA_SET:-rs0}"
MONGO_NODE_NAME="${MONGO_NODE_NAME:-mongo-1}"
MONGO_MEMBERS="${MONGO_MEMBERS:-mongo-1.mongo.internal:27017,mongo-2.mongo.internal:27017,mongo-3.mongo.internal:27017}"
MONGO_ROOT_USERNAME="${MONGO_ROOT_USERNAME:-admin}"
MONGO_ROOT_PASSWORD="${MONGO_ROOT_PASSWORD:-}"
MONGO_REPL_KEY="${MONGO_REPL_KEY:-}"
MONGOD_EXTRA_ARGS="${MONGOD_EXTRA_ARGS:-}"

if [[ -z "${MONGO_ROOT_PASSWORD}" ]]; then
  echo "MONGO_ROOT_PASSWORD is required" >&2
  exit 1
fi

if [[ -z "${MONGO_REPL_KEY}" ]]; then
  echo "MONGO_REPL_KEY is required" >&2
  exit 1
fi

mkdir -p /etc/mongo-secrets "${MONGO_DBPATH}"
KEYFILE_PATH="/etc/mongo-secrets/keyfile"
printf "%s" "${MONGO_REPL_KEY}" > "${KEYFILE_PATH}"
chmod 400 "${KEYFILE_PATH}"
chown mongodb:mongodb "${KEYFILE_PATH}" "${MONGO_DBPATH}"

term_handler() {
  if [[ -n "${MONGOD_PID:-}" ]] && kill -0 "${MONGOD_PID}" 2>/dev/null; then
    mongosh --quiet "mongodb://127.0.0.1:${MONGO_PORT}/admin" --eval 'db.adminCommand({ shutdown: 1, force: true })' >/dev/null 2>&1 || true
  fi
}
trap term_handler TERM INT

mongod \
  --bind_ip_all \
  --port "${MONGO_PORT}" \
  --dbpath "${MONGO_DBPATH}" \
  --replSet "${MONGO_RS_NAME}" \
  --keyFile "${KEYFILE_PATH}" \
  --auth \
  ${MONGOD_EXTRA_ARGS} &
MONGOD_PID=$!

wait_for_mongo() {
  until mongosh --quiet "mongodb://127.0.0.1:${MONGO_PORT}/admin" --eval 'db.runCommand({ ping: 1 }).ok' >/dev/null 2>&1; do
    sleep 2
  done
}

ensure_replset_and_admin_user() {
  local members_js
  local i=0
  members_js=""

  IFS=',' read -r -a members <<< "${MONGO_MEMBERS}"
  for member in "${members[@]}"; do
    if [[ -n "${members_js}" ]]; then
      members_js+=","
    fi
    members_js+="{ _id: ${i}, host: \"${member}\" }"
    i=$((i + 1))
  done

  mongosh --quiet "mongodb://127.0.0.1:${MONGO_PORT}/admin" <<MONGO_EOF
try {
  rs.status();
} catch (e) {
  if (e.code === 94 || (e.message || '').includes('not yet initialized')) {
    rs.initiate({
      _id: "${MONGO_RS_NAME}",
      members: [ ${members_js} ]
    });
  } else {
    throw e;
  }
}

let isMaster = db.hello();
let retries = 60;
while (!isMaster.isWritablePrimary && retries > 0) {
  sleep(2000);
  isMaster = db.hello();
  retries--;
}

const adminDb = db.getSiblingDB('admin');
if (!adminDb.getUser('${MONGO_ROOT_USERNAME}')) {
  adminDb.createUser({
    user: '${MONGO_ROOT_USERNAME}',
    pwd: '${MONGO_ROOT_PASSWORD}',
    roles: [{ role: 'root', db: 'admin' }]
  });
}
MONGO_EOF
}

wait_for_mongo

if [[ "${MONGO_NODE_NAME}" == "mongo-1" ]]; then
  ensure_replset_and_admin_user
fi

wait "${MONGOD_PID}"
