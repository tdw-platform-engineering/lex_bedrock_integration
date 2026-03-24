#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Public ECR Configuration
# Auth for public.ecr.aws must happen via us-east-1
PUBLIC_REGISTRY="public.ecr.aws/q7s8u3p2"
REPOSITORY_NAME="public-lambda-demo-lex-bedrock"
IMAGE_TAG="latest"
PLATFORM="linux/amd64"

usage() {
  cat <<'EOF'
Usage: ./deployment/deploy.sh [options]

Builds and pushes the container image to Public ECR.

Options:
  --tag <tag>           Image tag (default: latest)
  --platform <platform> Docker target platform (default: linux/amd64)
  -h, --help            Show help

Example:
  ./deployment/deploy.sh --tag 2026-03-20
EOF
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Error: '$1' is required but not installed." >&2
    exit 1
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tag)
      IMAGE_TAG="$2"
      shift 2
      ;;
    --platform)
      PLATFORM="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

require_cmd aws
require_cmd docker

IMAGE_URI="${PUBLIC_REGISTRY}/${REPOSITORY_NAME}:${IMAGE_TAG}"

# Ensure the Public Repository exists (using us-east-1 for public ECR API)
if ! aws ecr-public describe-repositories \
  --repository-names "${REPOSITORY_NAME}" \
  --region us-east-1 >/dev/null 2>&1; then
  echo "Public ECR repository '${REPOSITORY_NAME}' does not exist. Creating it..."
  aws ecr-public create-repository \
    --repository-name "${REPOSITORY_NAME}" \
    --region us-east-1 >/dev/null
fi

echo "Logging in to Public ECR..."
aws ecr-public get-login-password --region us-east-1 | docker login --username AWS --password-stdin public.ecr.aws

echo "Building and pushing image: ${IMAGE_URI}"
cd "${PROJECT_DIR}"

# Buildx is used to handle the platform flag and push in one step
docker buildx build \
  --platform "${PLATFORM}" \
  --provenance=false \
  --sbom=false \
  -t "${IMAGE_URI}" \
  --push \
  .

echo "----------------------------------------------------"
echo "Successfully pushed to: ${IMAGE_URI}"
echo "----------------------------------------------------"