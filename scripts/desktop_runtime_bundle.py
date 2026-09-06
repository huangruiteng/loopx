#!/usr/bin/env python3
"""Embed an exact public Git snapshot in the signed desktop distribution.

Never collect a developer's whole working directory or private local state.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import gzip
import subprocess


def build(root: Path) -> None:
    destination = root / "apps/desktop/loopx-control-plane/runtime"
    destination.mkdir(parents=True, exist_ok=True)
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    archive = destination / "runtime-source.tar.gz"
    subprocess.run([
        "git", "archive", "--format=tar.gz", f"--output={archive}", revision,
        "loopx", "scripts", "skills", "docs", "man", "examples", "apps/presentation",
        ".github", "README.md", "LICENSE", "pyproject.toml",
    ], cwd=root, check=True)
    entries = qualify_archive(archive)
    identity = {
        "schema_version": "desktop_runtime_bundle_v1",
        "source_revision": revision,
        "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
    }
    (destination / "identity.json").write_text(json.dumps(identity, indent=2) + "\n")
    print(f"Prepared exact desktop runtime: {revision[:12]} ({entries} installable entries)")


def qualify_archive(archive: Path) -> int:
    """Fail the release build when the App-side extractor could never install it.

    The Rust extractor iterates logical entries with the pinned tar crate's
    non-raw iterator: PAX local headers ('x', emitted by ``git archive`` for
    paths beyond ustar capacity), PAX global headers ('g') and GNU
    longname/longlink records ('L'/'K') carry path metadata for the entry that
    follows and are folded away before the App's ``is_file``/``is_dir`` checks
    run. The gate must therefore accept those metadata carriers and reject only
    entries that survive as real links, devices or reserved types -- shapes
    every client would fail the post-restart install (and repair) with
    ``runtime_bundle_invalid`` while the feed keeps advertising the update.
    Raw typeflag bytes are inspected precisely because tar readers silently
    fold extended headers; see bundled_runtime.rs tests for the matching
    extractor-side acceptance matrix.
    """
    metadata_typeflags = (b"g", b"x", b"L", b"K")
    entries = 0
    with gzip.open(archive, "rb") as bundle:
        while True:
            header = bundle.read(512)
            if len(header) < 512 or header.count(0) == 512:
                break
            typeflag = header[156:157]
            name = header[:100].rstrip(b"\0").decode("utf-8", "replace")
            if typeflag not in (b"0", b"\0", b"5") and typeflag not in metadata_typeflags:
                raise SystemExit(
                    f"runtime bundle entry is neither a file nor a directory, "
                    f"which the App cannot install: {name!r} "
                    f"(tar typeflag {typeflag!r})"
                )
            if typeflag in (b"0", b"\0", b"5"):
                entries += 1
            size = int((header[124:136].rstrip(b"\0 ") or b"0").decode("ascii") or "0", 8)
            bundle.read((size + 511) // 512 * 512)
    return entries


if __name__ == "__main__":
    build(Path(__file__).resolve().parents[1])
