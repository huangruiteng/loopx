from __future__ import annotations

import pytest

from loopx.cli import main


@pytest.mark.parametrize(
    "argv",
    [
        ["status", "--goal-id", "example-goal", "--project", "."],
        ["quota", "should-run", "--goal-id", "example-goal", "--project", "."],
    ],
)
def test_unsupported_project_option_is_not_misparsed_as_projection_cache_ttl(
    argv: list[str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(argv)

    assert exc_info.value.code == 2
    stderr = capsys.readouterr().err
    assert "unrecognized arguments: --project ." in stderr
    assert "projection-cache-ttl-seconds" not in stderr
    assert "invalid int value" not in stderr
