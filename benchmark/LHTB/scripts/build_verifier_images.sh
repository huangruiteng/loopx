#!/usr/bin/env bash
set -Eeuo pipefail

CODE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -z "${LHTB_ROOT:-}" ]]; then
  echo "FATAL: Set LHTB_ROOT to an LHTB checkout" >&2
  exit 1
fi
TASKS="$LHTB_ROOT/upstream/tasks"

LANGCHAIN_IMAGE="${LHTB_LANGCHAIN_VERIFIER_IMAGE:-lhtb-local/langchain-version-migration-verifier:20260826}"
NBODY_IMAGE="${LHTB_NBODY_VERIFIER_IMAGE:-lhtb-local/nbody-accel-iterative-verifier:20260826}"

build_if_missing() {
  local image="$1" dockerfile="$2" context="$3"
  if docker image inspect "$image" >/dev/null 2>&1; then
    echo "verifier image present: $image"
    return
  fi
  echo "building verifier image: $image"
  docker build --pull=false --file "$dockerfile" --tag "$image" "$context"
}

build_if_missing \
  "$LANGCHAIN_IMAGE" \
  "$CODE_DIR/verifier-images/langchain/Dockerfile" \
  "$TASKS/langchain-version-migration/tests"

build_if_missing \
  "$NBODY_IMAGE" \
  "$CODE_DIR/verifier-images/nbody/Dockerfile" \
  "$TASKS/nbody-accel-iterative/tests"

for image in "$LANGCHAIN_IMAGE" "$NBODY_IMAGE"; do
  docker run --rm --entrypoint /bin/sh "$image" \
    -c 'test -x /tests/test.sh && test -d /tests'
done

echo "verifier images ready"
