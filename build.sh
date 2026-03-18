#!/bin/bash
# Build and publish mcp-simple-pubmed: pip package + Docker image.
# Usage: ./build.sh
#
# Prerequisites:
#   pip install build twine
#   docker must be available
#
# The version is read automatically from pyproject.toml.

set -e

# Extract version from pyproject.toml
VERSION=$(grep '^version' pyproject.toml | sed 's/version = "\(.*\)"/\1/')
if [ -z "$VERSION" ]; then
    echo "ERROR: Could not read version from pyproject.toml"
    exit 1
fi
echo "Building version: $VERSION"

# --- Step 1: Build and push pip package ---
echo ""
echo "=== Building pip package ==="
rm -rf dist/
python -m build
echo ""
echo "=== Uploading to PyPI ==="
twine upload --skip-existing dist/*

# --- Step 2: Build Docker image ---
echo ""
echo "=== Building Docker image ==="
docker build -t mcp-simple-pubmed:${VERSION} -t mcp-simple-pubmed:latest .

echo ""
echo "=== Done ==="
echo "  pip: mcp-simple-pubmed ${VERSION} uploaded to PyPI"
echo "  docker: mcp-simple-pubmed:${VERSION} (also tagged as :latest)"
