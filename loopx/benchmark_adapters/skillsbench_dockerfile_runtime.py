from __future__ import annotations

import json
import os
import re
import shlex
import tempfile
from pathlib import Path

VENV_PIP_INVOCATION_MARKER = "# LOOPX_SKILLSBENCH_VENV_PIP_INVOCATION"
UBUNTU_APT_MIRROR_BEGIN = "# BEGIN LOOPX_SKILLSBENCH_UBUNTU_APT_MIRROR"
UBUNTU_APT_MIRROR_END = "# END LOOPX_SKILLSBENCH_UBUNTU_APT_MIRROR"
DEFAULT_UBUNTU_APT_MIRROR_BASE = "https://repo.huaweicloud.com/ubuntu"
DEFAULT_UBUNTU_APT_MIRROR_HOST = "repo.huaweicloud.com"
_BARE_PIP_INSTALL_RE = re.compile(
    r"(?P<prefix>^\s*(?:RUN\s+)?|(?:&&|\|\||;|\|)\s*)pip3?\s+install\b",
    re.IGNORECASE,
)
_APT_REPOSITORY_COMMAND_RE = re.compile(
    r"\bapt(?:-get)?\s+(?:update|install|download)\b",
    re.IGNORECASE,
)
_MAX_CONTEXT_FILES = 512
_MAX_CONTEXT_FILE_BYTES = 1024 * 1024


def _write_text_atomic(path: Path, text: str) -> None:
    fd, temp_name = tempfile.mkstemp(prefix=path.name, dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(temp_name, path)
    finally:
        Path(temp_name).unlink(missing_ok=True)


def _strip_marker_blocks(text: str, begin: str, end: str) -> str:
    pattern = re.compile(
        rf"^\s*{re.escape(begin)}\n.*?^\s*{re.escape(end)}\n?",
        re.MULTILINE | re.DOTALL,
    )
    return pattern.sub("", text)


def _stage_has_apt_update(lines: list[str]) -> bool:
    return bool(_APT_REPOSITORY_COMMAND_RE.search("\n".join(lines)))


def _dockerfile_logical_instructions(text: str) -> list[str]:
    instructions: list[str] = []
    pending: list[str] = []
    heredoc_delimiter: str | None = None
    for line in text.splitlines():
        if heredoc_delimiter is not None:
            if line.strip() == heredoc_delimiter:
                heredoc_delimiter = None
            continue
        heredoc_delimiter = dockerfile_heredoc_delimiter(line)
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        pending.append(stripped.rstrip("\\").rstrip())
        if stripped.endswith("\\"):
            continue
        instructions.append(" ".join(pending))
        pending = []
    if pending:
        instructions.append(" ".join(pending))
    return instructions


def _dockerfile_local_copy_sources(text: str) -> list[str]:
    sources: list[str] = []
    for instruction in _dockerfile_logical_instructions(text):
        match = re.match(r"^(?:COPY|ADD)\s+(.+)$", instruction, re.IGNORECASE)
        if match is None:
            continue
        body = match.group(1).strip()
        if re.match(r"^--from(?:=|\s)", body, re.IGNORECASE):
            continue
        while body.startswith("--"):
            flag, separator, remainder = body.partition(" ")
            if not separator or "=" not in flag:
                body = ""
                break
            body = remainder.lstrip()
        try:
            if body.startswith("["):
                values = json.loads(body)
                tokens = values if isinstance(values, list) else []
            else:
                tokens = shlex.split(body)
        except (json.JSONDecodeError, ValueError):
            continue
        tokens = [
            str(token)
            for token in tokens
            if isinstance(token, str) and not str(token).startswith("--")
        ]
        for source in tokens[:-1]:
            if "://" not in source and not source.startswith("--from="):
                sources.append(source)
    return sources


def _referenced_context_files(dockerfile: Path) -> list[Path]:
    context = dockerfile.parent.resolve()
    text = dockerfile.read_text(encoding="utf-8", errors="replace")
    files: list[Path] = []
    seen: set[Path] = set()
    for source in _dockerfile_local_copy_sources(text):
        if any(character in source for character in "*?["):
            matches = sorted(context.glob(source))
        else:
            matches = [context / source]
        for match in matches:
            try:
                if match.is_symlink():
                    continue
                resolved = match.resolve()
                if not resolved.is_relative_to(context):
                    continue
            except OSError:
                continue
            candidates = resolved.rglob("*") if resolved.is_dir() else (resolved,)
            for candidate in candidates:
                if len(files) >= _MAX_CONTEXT_FILES:
                    return files
                try:
                    if (
                        candidate in seen
                        or not candidate.is_file()
                        or candidate.is_symlink()
                        or candidate.stat().st_size > _MAX_CONTEXT_FILE_BYTES
                    ):
                        continue
                except OSError:
                    continue
                seen.add(candidate)
                files.append(candidate)
    return files


def copied_context_needs_apt_retry_patch(dockerfile: Path) -> bool:
    """Detect apt repository commands in local files copied into an image."""

    if not dockerfile.exists():
        return False
    for path in _referenced_context_files(dockerfile):
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if b"\x00" in data:
            continue
        if _APT_REPOSITORY_COMMAND_RE.search(data.decode("utf-8", errors="replace")):
            return True
    return False


def needs_apt_retry_patch(dockerfile: Path) -> bool:
    if not dockerfile.exists():
        return False
    text = dockerfile.read_text(encoding="utf-8", errors="replace")
    if re.search(r"^\s*FROM\s+scratch(?:\s|$)", text, re.IGNORECASE | re.MULTILINE):
        return False
    return bool(_APT_REPOSITORY_COMMAND_RE.search(text)) or (
        copied_context_needs_apt_retry_patch(dockerfile)
    )


def _dockerfile_stage_starts(lines: list[str]) -> list[int]:
    starts: list[int] = []
    heredoc_delimiter: str | None = None
    for index, line in enumerate(lines):
        if heredoc_delimiter is not None:
            if line.strip() == heredoc_delimiter:
                heredoc_delimiter = None
            continue
        heredoc_delimiter = dockerfile_heredoc_delimiter(line)
        if re.match(r"^\s*FROM\s+", line, re.IGNORECASE):
            starts.append(index)
    return starts


def needs_ubuntu_apt_mirror_patch(dockerfile: Path) -> bool:
    """Return whether a Dockerfile or copied setup file accesses apt.

    The staged patch is adaptive: it rewrites only Ubuntu source files found
    in the image, so Debian and other apt-based images are left unchanged.
    """

    if not dockerfile.exists():
        return False
    text = _strip_marker_blocks(
        dockerfile.read_text(encoding="utf-8", errors="replace"),
        UBUNTU_APT_MIRROR_BEGIN,
        UBUNTU_APT_MIRROR_END,
    )
    return _stage_has_apt_update(text.splitlines()) or (
        copied_context_needs_apt_retry_patch(dockerfile)
    )


def _ubuntu_apt_mirror_block() -> list[str]:
    return [
        UBUNTU_APT_MIRROR_BEGIN,
        f"ARG LOOPX_SKILLSBENCH_UBUNTU_APT_MIRROR={DEFAULT_UBUNTU_APT_MIRROR_BASE}",
        "RUN set -eux; \\",
        "    if [ -d /etc/apt ] && [ -w /etc/apt ]; then \\",
        "      find /etc/apt -type f \\",
        "        \\( -name '*.list' -o -name '*.sources' \\) \\",
        "        -exec sed -i \\",
        '          -e "s#https\\?://archive.ubuntu.com/ubuntu#${LOOPX_SKILLSBENCH_UBUNTU_APT_MIRROR}#g" \\',
        '          -e "s#https\\?://security.ubuntu.com/ubuntu#${LOOPX_SKILLSBENCH_UBUNTU_APT_MIRROR}#g" \\',
        "          {} +; \\",
        "      if [ -w /var/lib/apt/lists ]; then rm -rf /var/lib/apt/lists/*; fi; \\",
        "    else \\",
        "      echo 'loopx Ubuntu apt mirror skipped: apt directory is not writable'; \\",
        "    fi",
        UBUNTU_APT_MIRROR_END,
    ]


def patch_ubuntu_apt_mirror(dockerfile: Path) -> bool:
    """Add a staged-only Ubuntu apt mirror fallback to apt-using stages."""

    if not dockerfile.exists():
        return False
    original = dockerfile.read_text(encoding="utf-8", errors="replace")
    if UBUNTU_APT_MIRROR_BEGIN in original and UBUNTU_APT_MIRROR_END in original:
        return False
    text = _strip_marker_blocks(
        original,
        UBUNTU_APT_MIRROR_BEGIN,
        UBUNTU_APT_MIRROR_END,
    )
    lines = text.splitlines()
    stage_starts = _dockerfile_stage_starts(lines)
    if not stage_starts:
        return False
    copied_context_apt = copied_context_needs_apt_retry_patch(dockerfile)

    patched_lines = lines[: stage_starts[0]]
    applied = False
    for position, start in enumerate(stage_starts):
        end = (
            stage_starts[position + 1]
            if position + 1 < len(stage_starts)
            else len(lines)
        )
        stage_lines = lines[start:end]
        from_line = stage_lines[0].strip().lower()
        if (_stage_has_apt_update(stage_lines) or copied_context_apt) and not re.match(
            r"from(?:\s+--platform=\S+)?\s+scratch(?:\s|$)",
            from_line,
        ):
            patched_lines.extend(
                [stage_lines[0], "", *_ubuntu_apt_mirror_block(), "", *stage_lines[1:]]
            )
            applied = True
        else:
            patched_lines.extend(stage_lines)
    if not applied:
        return False
    patched = "\n".join(patched_lines).rstrip() + "\n"
    if patched == original:
        return False
    _write_text_atomic(dockerfile, patched)
    return True


def dockerfile_heredoc_delimiter(line: str) -> str | None:
    match = re.search(r"<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?", line)
    return match.group(1) if match else None


def _rewrite_bare_pip_installs(text: str) -> tuple[str, int]:
    lines: list[str] = []
    replaced = 0
    heredoc_delimiter: str | None = None
    for line in text.splitlines():
        if heredoc_delimiter is not None:
            lines.append(line)
            if line.strip() == heredoc_delimiter:
                heredoc_delimiter = None
            continue
        heredoc_delimiter = dockerfile_heredoc_delimiter(line)
        if line.lstrip().startswith("#"):
            lines.append(line)
            continue
        rewritten, count = _BARE_PIP_INSTALL_RE.subn(
            r"\g<prefix>python3 -m pip install", line
        )
        lines.append(rewritten)
        replaced += count
    suffix = "\n" if text.endswith("\n") else ""
    return "\n".join(lines) + suffix, replaced


def _stage_activates_venv(text: str) -> bool:
    has_venv = bool(re.search(r"\bpython\S*\s+-m\s+venv\s+", text, re.IGNORECASE))
    has_venv_path = bool(
        re.search(
            r"^\s*ENV\s+PATH=.*(?:VIRTUAL_ENV|venv).*/bin",
            text,
            re.MULTILINE | re.IGNORECASE,
        )
    )
    return has_venv and has_venv_path


def _rewrite_venv_stage_pip_installs(text: str) -> tuple[str, int]:
    lines = text.splitlines()
    stage_starts = [
        index
        for index, line in enumerate(lines)
        if re.match(r"^\s*FROM\s+", line, re.IGNORECASE)
    ]
    if not stage_starts:
        return text, 0

    rewritten_lines = lines[: stage_starts[0]]
    replaced = 0
    for position, start in enumerate(stage_starts):
        end = (
            stage_starts[position + 1]
            if position + 1 < len(stage_starts)
            else len(lines)
        )
        stage_text = "\n".join(lines[start:end])
        if _stage_activates_venv(stage_text):
            stage_text, stage_replaced = _rewrite_bare_pip_installs(stage_text)
            replaced += stage_replaced
        rewritten_lines.extend(stage_text.splitlines())
    suffix = "\n" if text.endswith("\n") else ""
    return "\n".join(rewritten_lines) + suffix, replaced


def needs_venv_pip_invocation_patch(dockerfile: Path) -> bool:
    if not dockerfile.exists():
        return False
    text = dockerfile.read_text(encoding="utf-8", errors="replace")
    return _rewrite_venv_stage_pip_installs(text)[1] > 0


def patch_venv_pip_invocations(dockerfile: Path) -> bool:
    """Keep pip installs bound to an explicitly activated Dockerfile venv."""

    if not needs_venv_pip_invocation_patch(dockerfile):
        return False
    original = dockerfile.read_text(encoding="utf-8")
    patched, _ = _rewrite_venv_stage_pip_installs(original)
    lines = patched.splitlines()
    from_index = next(
        (
            index
            for index, line in enumerate(lines)
            if line.lstrip().upper().startswith("FROM ")
        ),
        -1,
    )
    lines.insert(from_index + 1, VENV_PIP_INVOCATION_MARKER)
    patched = "\n".join(lines).rstrip() + "\n"
    fd, temp_name = tempfile.mkstemp(prefix=dockerfile.name, dir=dockerfile.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(patched)
        os.replace(temp_name, dockerfile)
    finally:
        Path(temp_name).unlink(missing_ok=True)
    return True
