#!/bin/bash
set -e

IMAGE=ghcr.io/ewasjon/lpprtklib-client-base:latest

docker buildx build \
    --platform linux/arm64 \
    -f Dockerfile.base \
    -t ${IMAGE} \
    --push \
    .

echo "Pushed ${IMAGE}"
