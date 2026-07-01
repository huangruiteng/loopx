from __future__ import annotations

# New lightweight research kernel. Keep this file small: user-facing
# auto-research additions should start here or in kernel.py, not in legacy_core.
from .kernel import (
    LIGHTWEIGHT_AUTO_RESEARCH_EVIDENCE_SCHEMA_VERSION,
    LIGHTWEIGHT_AUTO_RESEARCH_HYPOTHESIS_SCHEMA_VERSION,
    LIGHTWEIGHT_AUTO_RESEARCH_RESULT_SCHEMA_VERSION,
    lightweight_hypothesis,
    run_lightweight_auto_research,
)
