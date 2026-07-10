"""Runtime proxy evidence helpers for SkillsBench launches."""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Mapping, MutableMapping
from pathlib import Path
from typing import Any

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows import compatibility
    fcntl = None  # type: ignore[assignment]


BASE_IMAGE_PREWARM_TIMEOUT_SECONDS = 900.0
_DOCKERFILE_FROM_PATTERN = re.compile(
    r"^\s*FROM(?:\s+--platform=\S+)?\s+(?P<image>\S+)"
    r"(?:\s+AS\s+(?P<alias>\S+))?\s*$",
    flags=re.IGNORECASE,
)
_SAFE_IMAGE_REFERENCE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/:@+-]{0,511}$")


def apply_proxy_runtime_env(
    environ: MutableMapping[str, str],
    proxy_env: Mapping[str, str],
    docker_config_env: Mapping[str, str],
    *,
    plan: dict[str, Any] | None,
) -> None:
    environ.update(proxy_env)
    environ.update(docker_config_env)
    if not isinstance(plan, dict):
        return
    prerequisites = plan.setdefault("runner_prerequisites", {})
    if not isinstance(prerequisites, dict):
        return
    prerequisites["benchmark_egress_proxy_agent_env_injected"] = bool(proxy_env)
    if docker_config_env.get("DOCKER_CONFIG"):
        prerequisites["benchmark_egress_proxy_docker_config_injected"] = True
        prerequisites["benchmark_egress_proxy_docker_config_path_recorded"] = False
        prerequisites["benchmark_egress_proxy_docker_config_raw_proxy_recorded"] = False


def _docker_config_payload_with_proxy(*, proxy_url: str, no_proxy: str) -> dict[str, Any]:
    docker_config_dir = os.environ.get("DOCKER_CONFIG")
    source_config = (
        Path(docker_config_dir).expanduser() / "config.json"
        if docker_config_dir
        else Path.home() / ".docker" / "config.json"
    )
    payload: dict[str, Any] = {}
    if source_config.exists():
        try:
            loaded = json.loads(source_config.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            loaded = {}
        if isinstance(loaded, dict):
            payload = loaded
    proxies = payload.setdefault("proxies", {})
    if not isinstance(proxies, dict):
        proxies = {}
        payload["proxies"] = proxies
    proxies["default"] = {
        "httpProxy": proxy_url,
        "httpsProxy": proxy_url,
        "noProxy": no_proxy,
    }
    return payload


@contextlib.contextmanager
def proxy_runtime_env_applied(
    proxy_env: Mapping[str, str], *, plan: dict[str, Any] | None = None
) -> Any:
    if not proxy_env:
        yield
        return
    docker_config_tmp: tempfile.TemporaryDirectory[str] | None = None
    docker_config_env: dict[str, str] = {}
    proxy_url = proxy_env.get("LOOPX_SKILLSBENCH_EGRESS_PROXY", "")
    if proxy_url:
        docker_config_tmp = tempfile.TemporaryDirectory(
            prefix="loopx-skillsbench-docker-proxy-"
        )
        docker_config_path = Path(docker_config_tmp.name) / "config.json"
        docker_config_path.write_text(
            json.dumps(
                _docker_config_payload_with_proxy(
                    proxy_url=proxy_url,
                    no_proxy=proxy_env.get("NO_PROXY", "localhost,127.0.0.1,::1"),
                ),
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        docker_config_env["DOCKER_CONFIG"] = docker_config_tmp.name
    keys = set(proxy_env) | set(docker_config_env)
    previous = {key: os.environ.get(key) for key in keys}
    try:
        apply_proxy_runtime_env(os.environ, proxy_env, docker_config_env, plan=plan)
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        if docker_config_tmp is not None:
            docker_config_tmp.cleanup()


def dockerfile_external_base_images(dockerfile: Path) -> list[str]:
    """Return external FROM references while excluding scratch and stage aliases."""

    if not dockerfile.exists():
        return []
    try:
        lines = dockerfile.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    aliases: set[str] = set()
    images: list[str] = []
    seen: set[str] = set()
    for line in lines:
        match = _DOCKERFILE_FROM_PATTERN.match(line)
        if not match:
            continue
        image = match.group("image").strip()
        image_key = image.lower()
        if (
            image_key == "scratch"
            or image_key in aliases
            or "$" in image
            or not _SAFE_IMAGE_REFERENCE_PATTERN.fullmatch(image)
        ):
            alias = str(match.group("alias") or "").strip().lower()
            if alias:
                aliases.add(alias)
            continue
        if image not in seen:
            images.append(image)
            seen.add(image)
        alias = str(match.group("alias") or "").strip().lower()
        if alias:
            aliases.add(alias)
    return images


def _image_cached(docker_bin: str, image: str) -> bool:
    try:
        result = subprocess.run(
            [docker_bin, "image", "inspect", image],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def prewarm_dockerfile_base_images(
    dockerfile: Path,
    *,
    enabled: bool,
    timeout_seconds: float = BASE_IMAGE_PREWARM_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Load Dockerfile base images through proxy-aware skopeo into daemon cache."""

    images = dockerfile_external_base_images(dockerfile) if enabled else []
    docker_bin = shutil.which("docker") if images else None
    skopeo_bin = shutil.which("skopeo") if images else None
    metadata: dict[str, Any] = {
        "benchmark_egress_proxy_base_image_prewarm_status": (
            "pending" if images else "not_required"
        ),
        "benchmark_egress_proxy_base_image_prewarm_required": bool(images),
        "benchmark_egress_proxy_base_image_prewarm_docker_available": bool(docker_bin),
        "benchmark_egress_proxy_base_image_prewarm_skopeo_available": bool(skopeo_bin),
        "benchmark_egress_proxy_base_image_prewarm_candidate_count": len(images),
        "benchmark_egress_proxy_base_image_prewarm_attempted_count": 0,
        "benchmark_egress_proxy_base_image_prewarm_cache_hit_count": 0,
        "benchmark_egress_proxy_base_image_prewarm_loaded_count": 0,
        "benchmark_egress_proxy_base_image_prewarm_failed_count": 0,
        "benchmark_egress_proxy_base_image_prewarm_raw_image_refs_recorded": False,
        "benchmark_egress_proxy_base_image_prewarm_raw_output_recorded": False,
    }
    if not images:
        return metadata
    if not docker_bin or not skopeo_bin:
        metadata["benchmark_egress_proxy_base_image_prewarm_status"] = "tool_missing"
        return metadata

    timeout = max(30.0, float(timeout_seconds or 0.0))
    for image in images:
        if _image_cached(docker_bin, image):
            metadata["benchmark_egress_proxy_base_image_prewarm_cache_hit_count"] += 1
            continue
        lock_digest = hashlib.sha256(image.encode("utf-8")).hexdigest()[:16]
        lock_path = Path(tempfile.gettempdir()) / (
            f"loopx-skillsbench-image-prewarm-{lock_digest}.lock"
        )
        try:
            with lock_path.open("a", encoding="utf-8") as lock_file:
                if fcntl is not None:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                if _image_cached(docker_bin, image):
                    metadata[
                        "benchmark_egress_proxy_base_image_prewarm_cache_hit_count"
                    ] += 1
                    continue
                metadata[
                    "benchmark_egress_proxy_base_image_prewarm_attempted_count"
                ] += 1
                result = subprocess.run(
                    [
                        skopeo_bin,
                        "copy",
                        "--retry-times",
                        "3",
                        f"docker://{image}",
                        f"docker-daemon:{image}",
                    ],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                    timeout=timeout,
                )
        except (OSError, subprocess.TimeoutExpired):
            metadata["benchmark_egress_proxy_base_image_prewarm_failed_count"] += 1
            continue
        if result.returncode == 0:
            metadata["benchmark_egress_proxy_base_image_prewarm_loaded_count"] += 1
        else:
            metadata["benchmark_egress_proxy_base_image_prewarm_failed_count"] += 1

    failed = metadata["benchmark_egress_proxy_base_image_prewarm_failed_count"]
    if failed == 0:
        status = "completed"
    elif failed == len(images):
        status = "failed"
    else:
        status = "partial"
    metadata["benchmark_egress_proxy_base_image_prewarm_status"] = status
    return metadata


def compact_base_image_prewarm_fields(value: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    compact: dict[str, Any] = {}
    status = value.get("benchmark_egress_proxy_base_image_prewarm_status")
    if isinstance(status, str) and status:
        compact["benchmark_egress_proxy_base_image_prewarm_status"] = status[:80]
    for field in (
        "benchmark_egress_proxy_base_image_prewarm_required",
        "benchmark_egress_proxy_base_image_prewarm_docker_available",
        "benchmark_egress_proxy_base_image_prewarm_skopeo_available",
        "benchmark_egress_proxy_base_image_prewarm_raw_image_refs_recorded",
        "benchmark_egress_proxy_base_image_prewarm_raw_output_recorded",
    ):
        if isinstance(value.get(field), bool):
            compact[field] = value[field]
    for field in (
        "benchmark_egress_proxy_base_image_prewarm_candidate_count",
        "benchmark_egress_proxy_base_image_prewarm_attempted_count",
        "benchmark_egress_proxy_base_image_prewarm_cache_hit_count",
        "benchmark_egress_proxy_base_image_prewarm_loaded_count",
        "benchmark_egress_proxy_base_image_prewarm_failed_count",
    ):
        if isinstance(value.get(field), int) and not isinstance(value.get(field), bool):
            compact[field] = value[field]
    return compact
