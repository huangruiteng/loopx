"""Compatibility entry for existing Harbor agent configs.

Use benchmark.runtime.harbor:BenchmarkCodex with execution_mode for new studies.
Historical assisted WEN modes are retired; results remain tied to their old revision.
"""
import os
from benchmark.runtime.harbor import BenchmarkCodex

class CodexLoopxAgent(BenchmarkCodex):
    def __init__(self, *args, **kwargs):
        if any(os.environ.get(key) for key in ("WEN_MODE", "WEN_CLAIM_CODEX_APP", "LOOPX_UNGATED")):
            raise ValueError("Retired WEN controls: select an explicit execution_mode; see runtime/RUNTIME.md")
        kwargs.setdefault("execution_mode", "loopx-goal")
        super().__init__(*args, **kwargs)
