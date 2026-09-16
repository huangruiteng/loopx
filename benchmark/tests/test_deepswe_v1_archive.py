"""Archive verification remains strict after compilation and Git EOL conversion."""

import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
RELATIVE_ARCHIVE = Path("benchmark/deepswe-gptxhigh-v1")
spec = importlib.util.spec_from_file_location("check_deepswe_v1", ROOT / "benchmark/check_deepswe_v1.py")
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


@pytest.fixture
def archive(tmp_path):
    destination = tmp_path / "archive"
    shutil.copytree(ROOT / RELATIVE_ARCHIVE, destination)
    return destination


def test_premerge_compilation_preserves_identity(archive):
    before = checker.check_archive(archive)
    subprocess.run(
        [sys.executable, "-m", "py_compile", *map(str, archive.glob("*.py"))],
        check=True,
    )
    assert (archive / "__pycache__").is_dir()
    assert checker.check_archive(archive) == before
    shutil.copyfile(next((archive / "__pycache__").glob("*.pyc")), archive / "legacy.pyc")
    assert checker.check_archive(archive) == before


@pytest.mark.parametrize("mutation", ["byte", "mode", "source", "cache_source", "directory", "symlink", "cache_symlink"])
def test_archive_mutations_still_fail_closed(archive, mutation):
    if mutation == "byte":
        with (archive / "README.md").open("ab") as handle:
            handle.write(b"x")
    elif mutation == "mode":
        script = archive / "run_five_arms_remaining59_20260910.sh"
        script.chmod(script.stat().st_mode & ~0o111)
    elif mutation == "source":
        (archive / "extra.py").write_text("pass\n")
    elif mutation == "cache_source":
        (archive / "__pycache__").mkdir(exist_ok=True)
        (archive / "__pycache__/extra.py").write_text("pass\n")
    elif mutation == "directory":
        (archive / "extra").mkdir()
    else:
        destination = archive / "extra.pyc"
        if mutation == "cache_symlink":
            (archive / "__pycache__").mkdir(exist_ok=True)
            destination = archive / "__pycache__/extra.pyc"
        try:
            destination.symlink_to(archive / "README.md")
        except OSError:
            pytest.skip("symlinks unavailable")
    with pytest.raises(ValueError):
        checker.check_archive(archive)


def test_autocrlf_checkout_preserves_archive_bytes(tmp_path):
    repository = tmp_path / "repository"
    repository.mkdir()
    subprocess.run(["git", "init", "-q", str(repository)], check=True)
    shutil.copyfile(ROOT / ".gitattributes", repository / ".gitattributes")
    shutil.copytree(ROOT / RELATIVE_ARCHIVE, repository / RELATIVE_ARCHIVE,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    (repository / "control.txt").write_bytes(b"control\n")

    def git(*args):
        return subprocess.run(
            ["git", "-C", str(repository), "-c", "core.autocrlf=true", *args],
            check=True, capture_output=True, text=True,
        )

    git("add", ".gitattributes", str(RELATIVE_ARCHIVE), "control.txt")
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    git("checkout-index", "--all", f"--prefix={checkout.as_posix()}/")
    assert (checkout / "control.txt").read_bytes() == b"control\r\n"
    assert checker.check_archive(checkout / RELATIVE_ARCHIVE)["archive_tree"] == checker.EXPECTED_TREE
    for path in (ROOT / RELATIVE_ARCHIVE).iterdir():
        if path.is_file() and path.suffix != ".pyc":
            assert (checkout / RELATIVE_ARCHIVE / path.name).read_bytes() == path.read_bytes()
