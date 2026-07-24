from pathlib import Path

from loopx.benchmark_adapters import skillsbench_dockerfile_runtime as runtime


def _dockerfile(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "Dockerfile"
    path.write_text(text, encoding="utf-8")
    return path


def test_ubuntu_apt_mirror_patch_is_staged_per_apt_stage(tmp_path: Path) -> None:
    dockerfile = _dockerfile(
        tmp_path,
        "FROM alpine:3.20 AS source\n"
        "RUN echo source\n"
        "FROM ubuntu:24.04\n"
        "RUN apt-get update && apt-get install -y curl\n",
    )

    assert runtime.needs_ubuntu_apt_mirror_patch(dockerfile) is True
    assert runtime.patch_ubuntu_apt_mirror(dockerfile) is True

    patched = dockerfile.read_text(encoding="utf-8")
    assert patched.count(runtime.UBUNTU_APT_MIRROR_BEGIN) == 1
    assert runtime.DEFAULT_UBUNTU_APT_MIRROR_BASE in patched
    assert "archive.ubuntu.com/ubuntu" in patched
    assert "security.ubuntu.com/ubuntu" in patched
    assert runtime.patch_ubuntu_apt_mirror(dockerfile) is False


def test_ubuntu_apt_mirror_patch_skips_dockerfiles_without_apt(tmp_path: Path) -> None:
    dockerfile = _dockerfile(tmp_path, "FROM ubuntu:24.04\nRUN echo ready\n")

    assert runtime.needs_ubuntu_apt_mirror_patch(dockerfile) is False
    assert runtime.patch_ubuntu_apt_mirror(dockerfile) is False
    assert runtime.UBUNTU_APT_MIRROR_BEGIN not in dockerfile.read_text(encoding="utf-8")


def test_ubuntu_apt_mirror_patch_ignores_from_inside_heredoc(tmp_path: Path) -> None:
    dockerfile = _dockerfile(
        tmp_path,
        "FROM ubuntu:24.04\n"
        "RUN python3 <<'PY'\n"
        "FROM not-a-docker-stage\n"
        "PY\n"
        "RUN apt-get update\n",
    )

    assert runtime.patch_ubuntu_apt_mirror(dockerfile) is True

    patched = dockerfile.read_text(encoding="utf-8")
    assert patched.count(runtime.UBUNTU_APT_MIRROR_BEGIN) == 1
    assert patched.index(runtime.UBUNTU_APT_MIRROR_BEGIN) < patched.index("RUN python3")


def test_pip_no_build_isolation_flags_are_explicit_and_heredoc_safe() -> None:
    original = (
        "FROM python:3.12-slim\n"
        "RUN pip3 install numpy && python3 -m pip install cython\n"
        "RUN python -m pip install --no-build-isolation pandas\n"
        'RUN echo "pip install remains documentation"\n'
        "RUN python3 - <<'PY'\n"
        "pip install not-a-docker-command\n"
        "PY\n"
    )

    patched, count = runtime.add_pip_no_build_isolation_flags(original)

    assert count == 2
    assert "pip3 install --no-build-isolation numpy" in patched
    assert "python3 -m pip install --no-build-isolation cython" in patched
    assert patched.count("python -m pip install --no-build-isolation pandas") == 1
    assert 'echo "pip install remains documentation"' in patched
    assert "pip install not-a-docker-command" in patched
    assert runtime.add_pip_no_build_isolation_flags(patched) == (patched, 0)


def test_no_isolation_materializes_declared_build_prerequisites() -> None:
    original = (
        "FROM python:3.12-slim\n"
        "RUN pip install --no-cache-dir \\\n"
        '    "setuptools<81" \\\n'
        "    numpy==1.26.4 \\\n"
        "    batman-package==2.5.2\n"
    )
    flagged, flag_count = runtime.add_pip_no_build_isolation_flags(original)

    patched, prerequisite_count = (
        runtime.add_pip_no_isolation_build_prerequisite_steps(flagged)
    )

    prerequisite_step = (
        "RUN python3 -m pip install --no-cache-dir "
        "'setuptools<81' wheel numpy==1.26.4"
    )
    assert flag_count == 1
    assert prerequisite_count == 1
    assert runtime.PIP_NO_ISOLATION_BUILD_PREREQUISITES_MARKER in patched
    assert prerequisite_step in patched
    assert patched.index(prerequisite_step) < patched.index(
        "RUN pip install --no-build-isolation"
    )
    assert runtime.add_pip_no_isolation_build_prerequisite_steps(patched) == (
        patched,
        0,
    )


def test_no_isolation_prerequisite_step_requires_declared_numpy() -> None:
    original = (
        "FROM python:3.12-slim\n"
        "RUN pip install --no-build-isolation 'setuptools<81' package==1.0\n"
    )

    assert runtime.add_pip_no_isolation_build_prerequisite_steps(original) == (
        original,
        0,
    )
