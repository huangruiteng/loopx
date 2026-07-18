"""Compatibility imports for the OpenViking semantic-preference extension."""

from ...extensions.openviking_semantic_preference.provider import *  # noqa: F401,F403
from ...extensions.openviking_semantic_preference.provider import main as _main


if __name__ == "__main__":
    raise SystemExit(_main())
