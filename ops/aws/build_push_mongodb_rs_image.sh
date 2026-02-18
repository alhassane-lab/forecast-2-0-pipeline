#!/usr/bin/env bash
set -euo pipefail

AWS_REGION="${AWS_REGION:-eu-west-1}"
IMAGE_TAG="${IMAGE_TAG:-6.0-rs}"
REPO_NAME="${REPO_NAME:-forecast-mongodb-rs}"

if ! command -v aws >/dev/null 2>&1; then
  echo "aws cli is required" >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required" >&2
  exit 1
fi

AWS_ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
REPO_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${REPO_NAME}"

aws ecr describe-repositories --repository-names "${REPO_NAME}" --region "${AWS_REGION}" >/dev/null 2>&1 \
  || aws ecr create-repository --repository-name "${REPO_NAME}" --region "${AWS_REGION}" >/dev/null

aws ecr get-login-password --region "${AWS_REGION}" \
  | docker login --username AWS --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

docker build --platform linux/amd64 -t "${REPO_URI}:${IMAGE_TAG}" -f docker/mongodb-rs/Dockerfile docker/mongodb-rs

docker push "${REPO_URI}:${IMAGE_TAG}"

echo "pushed ${REPO_URI}:${IMAGE_TAG}"
