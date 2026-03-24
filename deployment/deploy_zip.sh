#!/usr/bin/env bash
set -euo pipefail

# ──────────────────────────────────────────────────────────────────────
# Package Lambda as a .zip for Terraform or direct upload.
#
# Installs deps, bundles src/ + deps, outputs the zip.
# Run from anywhere — paths are resolved relative to this script.
# ──────────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${PROJECT_DIR}/../.." && pwd)"

# Default output: where Terraform expects it
DEFAULT_ZIP_PATH="${REPO_ROOT}/deployment/terraform/modules/infra/zip/lambda-lex-bedrock.zip"

ZIP_OUTPUT="${DEFAULT_ZIP_PATH}"
PYTHON="python3"

usage() {
  cat <<'EOF'
Usage: ./deployment/deploy_zip.sh [options]

Packages the Lambda function as a .zip for Terraform deployment.

Options:
  --output <path>    Output zip path (default: deployment/terraform/modules/infra/zip/lambda-lex-bedrock.zip)
  --python <cmd>     Python command (default: python3)
  -h, --help         Show help

Examples:
  ./deployment/deploy_zip.sh
  ./deployment/deploy_zip.sh --output ./my-lambda.zip
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output) ZIP_OUTPUT="$2"; shift 2 ;;
    --python) PYTHON="$2";     shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
done

# Ensure output directory exists
mkdir -p "$(dirname "${ZIP_OUTPUT}")"

BUILD_DIR=$(mktemp -d)
trap 'rm -rf "${BUILD_DIR}"' EXIT

echo "==> Installing dependencies into temp dir"
${PYTHON} -m pip install \
  --target "${BUILD_DIR}" \
  --quiet \
  --no-user \
  --platform manylinux2014_x86_64 \
  --implementation cp \
  --python-version 3.12 \
  --only-binary=:all: \
  -r "${PROJECT_DIR}/requirements.txt" 2>/dev/null || \
${PYTHON} -m pip install \
  --target "${BUILD_DIR}" \
  --quiet \
  --no-user \
  -r "${PROJECT_DIR}/requirements.txt"

echo "==> Copying source code"
cp -r "${PROJECT_DIR}/src" "${BUILD_DIR}/src"

# Clean up unnecessary files
find "${BUILD_DIR}" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "${BUILD_DIR}" -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true
find "${BUILD_DIR}" -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
find "${BUILD_DIR}" -name "*.pyc" -delete 2>/dev/null || true

# Remove the old zip if it exists
rm -f "${ZIP_OUTPUT}"

echo "==> Creating zip: ${ZIP_OUTPUT}"
(cd "${BUILD_DIR}" && zip -r -q "${ZIP_OUTPUT}" .)

ZIP_SIZE=$(du -h "${ZIP_OUTPUT}" | cut -f1)
echo "==> Done: ${ZIP_OUTPUT} (${ZIP_SIZE})"
echo ""
echo "    Terraform will pick it up from: ${ZIP_OUTPUT}"
echo "    Run 'terraform apply' in deployment/terraform/ to deploy."
