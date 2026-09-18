"""Compatibility entry for existing LHTB Harbor configs."""
from benchmark.runtime.harbor import BenchmarkCodex

class LoopxHeartbeatCodex(BenchmarkCodex):
    @staticmethod
    def name() -> str:
        return "loopx-generic-cli-heartbeat-codex"
