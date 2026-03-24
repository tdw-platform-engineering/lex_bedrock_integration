#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

AWS_REGION="us-west-2"
AWS_ACCOUNT_ID=""
REPOSITORY_NAME="tdw/cuscatlan/lambda-demo-lex-bedrock"
IMAGE_TAG="latest"
PLATFORM="linux/amd64"
LAMBDA_FUNCTION_NAME=""
SKIP_LAMBDA_UPDATE="false"

usage() {
  cat <<'EOF'
Usage: ./deployment/deploy.sh [options]

Builds and pushes the Lambda container image to ECR using a single-manifest push
(provenance/SBOM disabled to avoid extra ECR artifacts). Optionally updates Lambda.

Options:
  --region <region>               AWS region (default: us-west-2)
  --account-id <account-id>       AWS account ID (default: from STS caller identity)
  --repository <name>             ECR repository name (default: tdw/cuscatlan/demo-connect-lex-bedrock)
  --tag <tag>                     Image tag (default: latest)
  --platform <platform>           Docker target platform (default: linux/amd64)
  --function-name <name>          Lambda function name to update
  --skip-lambda-update            Build/push only, skip Lambda update
  -h, --help                      Show help

Examples:
  ./deployment/deploy.sh
  ./deployment/deploy.sh --tag 2026-03-06
  ./deployment/deploy.sh --function-name demo-connect-lex-bedrock
  ./deployment/deploy.sh --skip-lambda-update --tag latest
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
    --region)
      AWS_REGION="$2"
      shift 2
      ;;
    --account-id)
      AWS_ACCOUNT_ID="$2"
      shift 2
      ;;
    --repository)
      REPOSITORY_NAME="$2"
      shift 2
      ;;
    --tag)
      IMAGE_TAG="$2"
      shift 2
      ;;
    --platform)
      PLATFORM="$2"
      shift 2
      ;;
    --function-name)
      LAMBDA_FUNCTION_NAME="$2"
      shift 2
      ;;
    --skip-lambda-update)
      SKIP_LAMBDA_UPDATE="true"
      shift
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

if [[ -z "${AWS_ACCOUNT_ID}" ]]; then
  AWS_ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text --region "${AWS_REGION}")"
fi

ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
IMAGE_URI="${ECR_REGISTRY}/${REPOSITORY_NAME}:${IMAGE_TAG}"

if ! aws ecr describe-repositories \
  --repository-names "${REPOSITORY_NAME}" \
  --region "${AWS_REGION}" >/dev/null 2>&1; then
  echo "ECR repository '${REPOSITORY_NAME}' does not exist. Creating it..."
  aws ecr create-repository \
    --repository-name "${REPOSITORY_NAME}" \
    --region "${AWS_REGION}" >/dev/null
fi

echo "Logging in to ECR: ${ECR_REGISTRY}"
aws ecr get-login-password --region "${AWS_REGION}" | docker login --username AWS --password-stdin "${ECR_REGISTRY}"

echo "Building and pushing image: ${IMAGE_URI}"
cd "${PROJECT_DIR}"
docker buildx build \
  --platform "${PLATFORM}" \
  --provenance=false \
  --sbom=false \
  -t "${IMAGE_URI}" \
  --push \
  .

echo "Image pushed successfully: ${IMAGE_URI}"

if [[ "${SKIP_LAMBDA_UPDATE}" == "true" ]]; then
  echo "Skipping Lambda update (--skip-lambda-update)."
  exit 0
fi

if [[ -z "${LAMBDA_FUNCTION_NAME}" ]]; then
  echo "No Lambda function name provided. Skipping Lambda update."
  echo "Use --function-name <name> to update the function image."
  exit 0
fi

echo "Updating Lambda function '${LAMBDA_FUNCTION_NAME}' with image '${IMAGE_URI}'"
aws lambda update-function-code \
  --function-name "${LAMBDA_FUNCTION_NAME}" \
  --image-uri "${IMAGE_URI}" \
  --region "${AWS_REGION}" >/dev/null

echo "Waiting for Lambda update to complete..."
aws lambda wait function-updated \
  --function-name "${LAMBDA_FUNCTION_NAME}" \
  --region "${AWS_REGION}"

echo "Deployment completed successfully."
