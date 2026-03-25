#!/bin/bash
set -e

IMAGE=ghcr.io/ewasjon/lpprtklib-client
TAG=${1:-latest}

docker buildx build \
    --platform linux/arm64 \
    -f Dockerfile.local \
    -t ${IMAGE}:${TAG} \
    --push \
    .

echo "Pushed ${IMAGE}:${TAG}"
