#!/usr/bin/env python3
"""Smoke-test provider-neutral static packaging, rollback, and HTTP readback."""

from __future__ import annotations

import sys
import tempfile
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.presentation.static_site import (  # noqa: E402
    RECEIPT_FILE,
    package_static_site,
    rollback_static_site,
    verify_static_site_readback,
)


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, _format: str, *_args: object) -> None:
        return None


def package(
    site: Path, output: Path, state: Path, *, revision: str
) -> dict[str, object]:
    return package_static_site(
        site_dir=site,
        output_dir=output,
        state_dir=state,
        site_id="static-presentation-smoke",
        revision=revision,
        publisher_kind="local",
        desktop_visual_check="passed",
        mobile_visual_check="passed",
        link_check="passed",
        execute=True,
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-static-presentation-") as temp:
        root = Path(temp)
        site = root / "site"
        output = root / "publish"
        state = root / "state"
        site.mkdir()
        (site / "index.html").write_text("<h1>revision one</h1>\n", encoding="utf-8")

        first = package(site, output, state, revision="revision-one")
        if first["write_performed"] is not True:
            raise AssertionError(first)
        repeated = package(site, output, state, revision="equivalent-alias")
        if (
            repeated["semantic_noop"] is not True
            or repeated["active_revision"] != "revision-one"
        ):
            raise AssertionError(repeated)

        (site / "index.html").write_text("<h1>revision two</h1>\n", encoding="utf-8")
        second = package(site, output, state, revision="revision-two")
        if second["previous_revision"] != "revision-one":
            raise AssertionError(second)
        rollback = rollback_static_site(
            output_dir=output, state_dir=state, execute=True
        )
        if rollback["active_revision"] != "revision-one":
            raise AssertionError(rollback)

        handler = partial(_QuietHandler, directory=str(output))
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            receipt_url = f"http://127.0.0.1:{server.server_port}/{RECEIPT_FILE}"
            verified = verify_static_site_readback(
                output_dir=output,
                state_dir=state,
                receipt_url=receipt_url,
                retry_delay_seconds=0,
                execute=True,
            )
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()
        if verified["verified"] is not True or verified["revision"] != "revision-one":
            raise AssertionError(verified)

    print("static-site-presentation-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
