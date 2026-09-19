from __future__ import annotations

import os
from typing import Any

__version__ = "0.11.0"
API_VERSION = 1

# The 0.11.0 release exports no wire schema; the metadata-runtimes wheels do.
# Tests opt into the newer shape by setting this variable for the helper process.
_schema = os.environ.get("LOOPX_FAKE_NOKV_PROTOCOL_SCHEMA")
if _schema:
    WORKSPACE_PROTOCOL_SCHEMA = _schema


class RoutingConfig:
    # Union of the two real wheels the helper is qualified against: the 0.11.0
    # release provides etcd/static, the metadata-runtimes line provides seeds.
    # LOOPX_FAKE_NOKV_RELEASE_SHAPE=1 narrows the fixture to the release shape
    # so a seeds configuration reaches the helper's capability-mismatch path.
    if os.environ.get("LOOPX_FAKE_NOKV_RELEASE_SHAPE") != "1":

        @staticmethod
        def seeds(endpoints: list[str]) -> object:
            return ("seeds", endpoints)

    @staticmethod
    def etcd(endpoints: list[str], key_prefix: str, lease_ttl_seconds: int) -> object:
        return ("etcd", endpoints, key_prefix, lease_ttl_seconds)

    @staticmethod
    def static(*values: Any) -> object:
        return ("static", values)


class ObjectStoreConfig:
    @staticmethod
    def memory() -> object:
        return ("memory",)

    @staticmethod
    def s3(**values: Any) -> object:
        return ("s3", values)


class Client:
    def __init__(self, **_values: Any) -> None:
        self._bytes: bytes | None = None
        self._generation: int | None = None

    def find_workspaces(self, **_values: Any) -> dict[str, Any]:
        return {
            "workspaces": [
                {
                    "workspace": {
                        "workbench": "authority-workbench",
                        "workspace_incarnation_id": "a" * 32,
                    }
                }
            ],
            "next_cursor": None,
        }

    def read(self, workbench: str, path: str) -> dict[str, Any]:
        if self._bytes is None or self._generation is None:
            raise FileNotFoundError("missing")
        return {
            "bytes": self._bytes,
            "metadata": {
                "workbench": workbench,
                "path": path,
                "workspace_incarnation_id": "a" * 32,
                "generation": self._generation,
            },
        }

    def publish_bytes(
        self,
        workbench: str,
        path: str,
        payload: bytes,
        **values: Any,
    ) -> dict[str, Any]:
        expected = values["expected_generation"]
        if expected is None and self._generation is not None:
            raise FileExistsError("already exists")
        if expected is not None and expected != self._generation:
            raise RuntimeError("generation conflict")
        self._generation = (self._generation or 0) + 1
        self._bytes = payload
        return {
            "operation_id": values["operation_id"],
            "artifact_revision_id": values["artifact_revision_id"],
            "workbench": workbench,
            "path": path,
            "generation": self._generation,
        }
