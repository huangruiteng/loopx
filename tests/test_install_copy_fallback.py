import os
from pathlib import Path
import subprocess


def test_clone_failure_discards_only_partial_staging_target(tmp_path):
    script = (Path(__file__).parents[1] / "scripts/install-local.sh").read_text()
    function = script.split("copy_path() {", 1)[1].split("\n}\n", 1)[0]
    source, destination = tmp_path / "source tree", tmp_path / "staged tree"
    source.mkdir()
    (source / "keep.txt").write_text("original")
    binaries = tmp_path / "bin"
    binaries.mkdir()
    copier = binaries / "cp"
    copier.write_text(
        '#!/bin/sh\nif [ "$1" = "-cR" ]; then mkdir -p "$3"; touch "$3/partial"; exit 1; fi\nexec /bin/cp "$@"\n'
    )
    copier.chmod(0o755)
    result = subprocess.run(
        [
            "bash",
            "-c",
            "set -eu\ncopy_platform=Darwin\ncopy_path() {"
            + function
            + '\n}\ncopy_path "$1" "$2"',
            "copy-test",
            str(source),
            str(destination),
        ],
        env={**os.environ, "PATH": f"{binaries}:{os.environ['PATH']}"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert sorted(p.name for p in destination.iterdir()) == ["keep.txt"]
    (destination / "keep.txt").write_text("changed")
    assert (source / "keep.txt").read_text() == "original"
