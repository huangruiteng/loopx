#!/usr/bin/env bash
set -euo pipefail

repo="${LOOPX_REPO:-huangruiteng/loopx}"
ref="${LOOPX_REF:-stable}"
archive_url_override="${LOOPX_ARCHIVE_URL:-}"
archive_url="$archive_url_override"
python_bin="${LOOPX_PYTHON:-python3}"
export LOOPX_REPO="$repo"
export LOOPX_REF="$ref"

need() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "loopx installer error: missing required command: $1" >&2
    exit 1
  fi
}

need curl
need tar
need "$python_bin"

if [[ -n "${LOOPX_RESOLVED_SOURCE_GIT_COMMIT:-}" \
  && ! "$LOOPX_RESOLVED_SOURCE_GIT_COMMIT" =~ ^[0-9a-fA-F]{40}$ ]]; then
  echo "loopx installer error: LOOPX_RESOLVED_SOURCE_GIT_COMMIT must be a full Git commit SHA" >&2
  exit 2
fi

if [[ -z "$archive_url" ]]; then
  if [[ ! "$repo" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]]; then
    echo "loopx installer error: LOOPX_REPO must use GitHub owner/name syntax" >&2
    exit 2
  fi
  commit_api_url="$("$python_bin" - "$repo" "$ref" <<'PY'
from urllib.parse import quote
import sys

repo, ref = sys.argv[1:]
owner, name = repo.split("/", 1)
print(
    "https://api.github.com/repos/"
    f"{quote(owner, safe='')}/{quote(name, safe='')}/commits/{quote(ref, safe='')}"
)
PY
)"
  commit_json="$(curl -fsSL \
    -H 'Accept: application/vnd.github+json' \
    -H 'User-Agent: LoopX-installer' \
    "$commit_api_url")"
  resolved_commit="$(LOOPX_COMMIT_JSON="$commit_json" "$python_bin" - <<'PY'
import json
import os

payload = json.loads(os.environ["LOOPX_COMMIT_JSON"])
sha = payload.get("sha")
if not isinstance(sha, str) or len(sha) != 40:
    raise SystemExit("GitHub commit response did not include a full SHA")
print(sha)
PY
)"
  export LOOPX_RESOLVED_SOURCE_GIT_COMMIT="$resolved_commit"
  archive_url="https://codeload.github.com/$repo/tar.gz/$resolved_commit"
fi
export LOOPX_ARCHIVE_URL="$archive_url"

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
archive_sha256="$("$python_bin" - "$archive_path" <<'PY'
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
