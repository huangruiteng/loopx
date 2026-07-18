#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
package_source="$repo_root/integrations/pi"
install_root="${LOOPX_PI_INSTALL_ROOT:-$HOME/.local/share/loopx}"
package_target="$install_root/pi-package"
managed_marker="$package_target/.loopx-managed-pi-package"
pi_bin="${PI_BIN:-pi}"

usage() {
  printf '%s\n' \
    'Usage: scripts/install-pi-package.sh [--dry-run]' \
    '' \
    "Register the opt-in LoopX pi package in pi's user settings. This command" \
    'does not install a scheduler or modify resources for any other agent host.'
}

case "${1:-}" in
  "") ;;
  --dry-run)
    printf 'sync %q -> %q\n' "$package_source" "$package_target"
    printf '%q install %q\n' "$pi_bin" "$package_target"
    exit 0
    ;;
  -h|--help)
    usage
    exit 0
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac

if [[ ! -f "$package_source/package.json" ]]; then
  echo "loopx pi installer error: package not found: $package_source" >&2
  exit 1
fi

if ! command -v "$pi_bin" >/dev/null 2>&1; then
  echo "loopx pi installer error: pi executable not found: $pi_bin" >&2
  exit 1
fi

mkdir -p "$install_root"
if [[ -e "$package_target" && ! -f "$managed_marker" ]]; then
  echo "loopx pi installer error: refusing to replace unmanaged path: $package_target" >&2
  exit 1
fi

staging="$(mktemp -d "$install_root/.pi-package-stage.XXXXXX")"
backup=""
cleanup() {
  if [[ -n "$staging" && -d "$staging" ]]; then
    rm -rf "$staging"
  fi
}
trap cleanup EXIT

cp -R "$package_source/." "$staging/"
touch "$staging/.loopx-managed-pi-package"

if [[ -e "$package_target" ]]; then
  backup="$install_root/.pi-package-backup.$$"
  mv "$package_target" "$backup"
fi
if ! mv "$staging" "$package_target"; then
  if [[ -n "$backup" && -e "$backup" ]]; then
    mv "$backup" "$package_target"
  fi
  exit 1
fi
staging=""

if ! "$pi_bin" install "$package_target"; then
  rm -rf "$package_target"
  if [[ -n "$backup" && -e "$backup" ]]; then
    mv "$backup" "$package_target"
  fi
  exit 1
fi

if [[ -n "$backup" && -e "$backup" ]]; then
  rm -rf "$backup"
fi

echo "loopx pi package registered: $package_target"
echo "Run /reload in an already open pi session."
