from __future__ import annotations


LOOPX_COMMAND_INSTRUMENTATION_SOURCE = r'''
_SHELL_COMMAND_PREFIXES = {
    "if", "then", "elif", "else", "while", "until", "do", "!", "time", "{",
}
_SHELL_COMMAND_WRAPPERS = {"command", "exec", "builtin", "nohup"}
_NESTED_SHELLS = {"sh", "bash", "dash", "zsh", "ksh"}

def _shell_tokens(command: str) -> list[str]:
    try:
        lexer = shlex.shlex(
            command or "",
            posix=True,
            punctuation_chars=";&|()" + chr(10),
        )
        lexer.whitespace = " " + chr(9) + chr(13)
        lexer.whitespace_split = True
        lexer.commenters = ""
        return list(lexer)
    except ValueError:
        return (command or "").replace(chr(10), " ; ").split()

def _shell_basename(token: str) -> str:
    return token.rsplit("/", 1)[-1]

def _shell_separator(token: str) -> bool:
    return bool(token) and all(char in ";&|()" or char == chr(10) for char in token)

def _nested_shell_command(tokens: list[str], index: int) -> str | None:
    cursor = index + 1
    while cursor < len(tokens) and not _shell_separator(tokens[cursor]):
        option = tokens[cursor]
        if option == "--":
            cursor += 1
            continue
        if option == "--command" or (
            option.startswith("-")
            and not option.startswith("--")
            and "c" in option[1:]
        ):
            return tokens[cursor + 1] if cursor + 1 < len(tokens) else None
        if not option.startswith("-"):
            return None
        cursor += 1
    return None

def loopx_invocation_argvs(command: str, *, _depth: int = 0) -> list[list[str]]:
    tokens = _shell_tokens(command)
    invocations: list[list[str]] = []
    assignment_re = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=.*$")
    expect_command = True
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if _shell_separator(token):
            expect_command = True
            index += 1
            continue
        if not expect_command:
            index += 1
            continue
        basename = _shell_basename(token)
        if token in _SHELL_COMMAND_PREFIXES or assignment_re.match(token):
            index += 1
            continue
        if basename in _SHELL_COMMAND_WRAPPERS:
            index += 1
            while index < len(tokens) and tokens[index].startswith("-"):
                index += 1
            continue
        if basename == "env":
            index += 1
            while index < len(tokens) and (
                tokens[index].startswith("-") or assignment_re.match(tokens[index])
            ):
                index += 1
            continue
        if basename in _NESTED_SHELLS:
            nested = _nested_shell_command(tokens, index)
            if nested is not None:
                if _depth < 4:
                    invocations.extend(loopx_invocation_argvs(nested, _depth=_depth + 1))
                elif any(
                    _shell_basename(item) == "loopx" for item in _shell_tokens(nested)
                ):
                    # Depth-limited nested shell requests are ambiguous; reject closed.
                    invocations.extend([["loopx"], ["loopx"]])
            expect_command = False
            index += 1
            continue
        if basename == "loopx":
            end = index + 1
            while end < len(tokens) and not _shell_separator(tokens[end]):
                end += 1
            invocations.append(tokens[index:end])
        expect_command = False
        index += 1
    return invocations

def loopx_subcommands(command: str) -> list[str]:
    invocations = loopx_invocation_argvs(command)
    if not invocations:
        return []
    tokens = invocations[0]
    out: list[str] = []
    skip = False
    valued_options = {
        "--goal-id", "--todo-id", "--claimed-by", "--status", "--note",
        "--evidence", "--classification", "--registry", "--runtime-root",
        "--slots", "--source", "--format", "--project", "--goal-text",
        "--agent-id", "--host-surface", "--role", "--task-class",
        "--action-kind", "--text",
    }
    for token in tokens[1:]:
        if skip:
            skip = False
            continue
        if token.startswith("--"):
            if "=" not in token and token in valued_options:
                skip = True
            continue
        if token.startswith("-"):
            continue
        if re.match(r"^[A-Za-z][A-Za-z0-9_-]{0,40}$", token):
            out.append(token)
            if len(out) >= 2:
                break
    return out

def loopx_invocation_count(command: str) -> int:
    return len(loopx_invocation_argvs(command))

def enforce_single_loopx_invocation(count, record, append_record) -> None:
    if count <= 1:
        return
    stderr_text = (
        "bridge request rejected: send exactly one LoopX CLI command per "
        "operation=exec request" + chr(10)
    )
    complete_record = dict(record)
    complete_record.update({
        "record_phase": "complete",
        "returncode": 2,
        "success": False,
        "stdout_bytes": 0,
        "stderr_bytes": len(stderr_text.encode("utf-8")),
        "failure_category": "multiple_loopx_commands_per_bridge_request",
    })
    append_record(complete_record)
    sys.stderr.write(stderr_text)
    raise SystemExit(2)
'''.strip()
