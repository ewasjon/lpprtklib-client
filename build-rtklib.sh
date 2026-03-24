#!/bin/bash
set -e

IMAGE=ghcr.io/ewasjon/rtklib:latest

RTKLIB_REPO=${RTKLIB_REPO:-https://github.com/ewasjon/RTKLIB.git}

docker buildx build \
    --platform linux/arm64 \
    --build-arg TARGETARCH=arm64 \
    --build-arg RTKLIB_REPO=${RTKLIB_REPO} \
    -f Dockerfile.rtklib \
    -t ${IMAGE} \
    --push \
    .

echo "Pushed ${IMAGE}"
