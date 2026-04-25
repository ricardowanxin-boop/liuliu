#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FUNCTION_DIR="$ROOT_DIR/cloudbase/image-workshop-api"
BUILD_DIR="$ROOT_DIR/.cloudbase-build/image-workshop-api"
DIST_DIR="$ROOT_DIR/dist"
ZIP_PATH="$DIST_DIR/image-workshop-api-cloudbase.zip"

rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR" "$DIST_DIR"

cp "$FUNCTION_DIR/app.py" "$BUILD_DIR/app.py"
cp "$FUNCTION_DIR/scf_bootstrap" "$BUILD_DIR/scf_bootstrap"
cp "$FUNCTION_DIR/requirements.txt" "$BUILD_DIR/requirements.txt"
cp -R "$ROOT_DIR/backend" "$BUILD_DIR/backend"

find "$BUILD_DIR/backend" -type d -name "__pycache__" -prune -exec rm -rf {} +
find "$BUILD_DIR/backend" -type f -name "*.pyc" -delete
chmod +x "$BUILD_DIR/scf_bootstrap"

CLOUDBASE_PYTHON_VERSION="${CLOUDBASE_PYTHON_VERSION:-3.11}"
CLOUDBASE_PLATFORM="${CLOUDBASE_PLATFORM:-manylinux2014_x86_64}"

python3 -m pip install \
  --target "$BUILD_DIR/third_party" \
  --requirement "$BUILD_DIR/requirements.txt" \
  --platform "$CLOUDBASE_PLATFORM" \
  --implementation cp \
  --python-version "$CLOUDBASE_PYTHON_VERSION" \
  --only-binary=:all:

find "$BUILD_DIR/third_party" -type d -name "__pycache__" -prune -exec rm -rf {} +
find "$BUILD_DIR/third_party" -type f -name "*.pyc" -delete

rm -f "$ZIP_PATH"
(
  cd "$BUILD_DIR"
  zip -qr "$ZIP_PATH" .
)

echo "$ZIP_PATH"
