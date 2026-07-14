from __future__ import annotations

import re
from urllib.parse import urlsplit


CANONICAL_REPOSITORY_IDENTITY_PATTERN = re.compile(
    r"^git:(?P<host>[a-z0-9.-]+(?::[0-9]{1,5})?)/"
    r"(?P<path>[A-Za-z0-9._~+/-]+)$"
)


def normalize_repository_identity(remote_url_or_identity: str) -> str:
    """Return a credential-free identity shared by common Git transports."""

    raw = str(remote_url_or_identity or "").strip()
    if not raw:
        raise ValueError("repository remote or identity is required")

    canonical = CANONICAL_REPOSITORY_IDENTITY_PATTERN.fullmatch(raw)
    if canonical:
        path = _normalize_repository_path(canonical.group("path"))
        return f"git:{canonical.group('host').casefold()}/{path}"

    scp_match = re.fullmatch(r"(?:[^@/]+@)?([^:/]+):(.+)", raw)
    if scp_match and "://" not in raw:
        raw = f"ssh://{scp_match.group(1)}/{scp_match.group(2)}"

    parsed = urlsplit(raw)
    if (
        parsed.scheme not in {"git", "http", "https", "ssh"}
        or not parsed.hostname
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("repository remote must be a supported credential-free URL")

    host = parsed.hostname.casefold()
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("repository remote has an invalid port") from exc
    if port and not (
        (parsed.scheme in {"http", "git"} and port == 80)
        or (parsed.scheme in {"https", "ssh"} and port in {22, 443})
    ):
        host = f"{host}:{port}"

    path = _normalize_repository_path(parsed.path)
    return f"git:{host}/{path}"


def _normalize_repository_path(value: str) -> str:
    path = re.sub(r"/+", "/", str(value or "")).strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    if not path or any(segment in {".", ".."} for segment in path.split("/")):
        raise ValueError("repository remote must include a safe repository path")
    return path
