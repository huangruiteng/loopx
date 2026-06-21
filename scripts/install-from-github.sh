#!/usr/bin/env bash
set -euo pipefail

repo="${LOOPX_REPO:-huangruiteng/loopx}"
ref="${LOOPX_REF:-main}"
archive_url="${LOOPX_ARCHIVE_URL:-https://codeload.github.com/$repo/tar.gz/$ref}"

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
tar -xzf "$archive_path" -C "$extract_dir"

repo_root="$(find "$extract_dir" -mindepth 1 -maxdepth 1 -type d -print -quit)"
if [[ -z "$repo_root" || ! -x "$repo_root/scripts/install-local.sh" ]]; then
  echo "loopx installer error: downloaded archive does not contain scripts/install-local.sh" >&2
  exit 1
fi

# The downloaded checkout is temporary. Install a stable release snapshot and
# skip the live canary symlink unless the caller explicitly overrides it.
export LOOPX_INSTALL_CANARY="${LOOPX_INSTALL_CANARY:-0}"

"$repo_root/scripts/install-local.sh"
