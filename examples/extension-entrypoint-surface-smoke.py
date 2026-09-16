#!/usr/bin/env python3
"""Guard the entrypoints every extension manifest declares.

Manifest loading is deliberately import-free, so ``python_module``, hook
``factory`` and presentation ``view_validator`` references are only checked for
shape. A renamed or removed object therefore survives manifest validation and
only fails when a user activates the extension. This smoke resolves every
declared reference in the bundled and co-located manifests against the
repository source tree, without importing provider code.
"""

from __future__ import annotations

from pathlib import Path

from loopx.extensions.entrypoint_surface import (
    EntrypointKind,
    render_report,
    resolve_declared_entrypoints,
)


ROOT = Path(__file__).resolve().parents[1]

EXPECTED_KINDS = frozenset(kind.value for kind in EntrypointKind)

REQUIRED_KINDS = (
    EntrypointKind.PYTHON_MODULE.value,
    EntrypointKind.CONSOLE_SCRIPT.value,
    EntrypointKind.HOOK_FACTORY.value,
    EntrypointKind.VIEW_VALIDATOR.value,
)


def main() -> int:
    report = resolve_declared_entrypoints(ROOT)
    print(render_report(report))
    if not report.ok:
        return 1

    assert report.manifest_count > 0, "expected bundled extension manifests"
    assert report.entrypoints, "expected declared extension entrypoints"

    kinds = {item.kind.value for item in report.entrypoints}
    assert kinds <= EXPECTED_KINDS, kinds
    for required in REQUIRED_KINDS:
        assert required in kinds, f"no manifest declares a {required} entrypoint: {sorted(kinds)}"

    print("extension-entrypoint-surface-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
