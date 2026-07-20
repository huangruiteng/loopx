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
