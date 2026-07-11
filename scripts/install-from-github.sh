#!/usr/bin/env bash
set -euo pipefail

repo="${LOOPX_REPO:-huangruiteng/loopx}"
ref="${LOOPX_REF:-stable}"
archive_url="${LOOPX_ARCHIVE_URL:-https://codeload.github.com/$repo/tar.gz/$ref}"
export LOOPX_REPO="$repo"
export LOOPX_REF="$ref"
export LOOPX_ARCHIVE_URL="$archive_url"

need() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "loopx installer error: missing required command: $1" >&2
    exit 1
  fi
}

need curl
need tar
need python3

tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/loopx-install.XXXXXX")"
cleanup() {
  rm -rf "$tmp_dir"
}
trap cleanup EXIT

archive_path="$tmp_dir/loopx.tar.gz"
extract_dir="$tmp_dir/extract"
mkdir -p "$extract_dir"

echo "loopx installer: downloading $archive_url" >&2
curl -fsSL "$archive_url" -o "$archive_path"
archive_sha256="$(python3 - "$archive_path" <<'PY'
from pathlib import Path
import hashlib
import sys

digest = hashlib.sha256()
with Path(sys.argv[1]).open("rb") as handle:
    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
        digest.update(chunk)
print(digest.hexdigest())
PY
)"
export LOOPX_ARCHIVE_SHA256="$archive_sha256"
tar -xzf "$archive_path" -C "$extract_dir"

repo_root="$(find "$extract_dir" -mindepth 1 -maxdepth 1 -type d -print -quit)"
if [[ -z "$repo_root" || ! -x "$repo_root/scripts/install-local.sh" ]]; then
  echo "loopx installer error: downloaded archive does not contain scripts/install-local.sh" >&2
  exit 1
fi

# The downloaded checkout is temporary. Install a stable release snapshot and
# skip the live canary symlink unless the caller explicitly overrides it.
export LOOPX_INSTALL_CANARY="${LOOPX_INSTALL_CANARY:-0}"
export LOOPX_PROMOTE_DEFAULT="${LOOPX_PROMOTE_DEFAULT:-1}"
export LOOPX_PROMOTION_MODE="${LOOPX_PROMOTION_MODE:-trusted_github_archive}"

"$repo_root/scripts/install-local.sh"
