#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from loopx.capabilities.issue_fix import build_issue_fix_pr_description  # noqa: E402


BASE = "## Motivation\n\nFix the reproduced behavior.\n"
PREFERENCE_REF = "viking://user/preferences/pr-description-chinese"


with tempfile.TemporaryDirectory(prefix="loopx-issue-fix-description-") as raw_temp:
    temp = Path(raw_temp)
    project = temp / "project"
    project.mkdir()
    counter = temp / "provider-count.txt"
    provider = temp / "provider.py"
    provider.write_text(
        """import json, sys
from pathlib import Path
counter = Path(sys.argv[1])
count = int(counter.read_text() or "0") if counter.exists() else 0
counter.write_text(str(count + 1))
json.load(sys.stdin)
json.dump({
    "schema_version": "semantic_preference_provider_response_v0",
    "items": [{
        "preference_ref": "viking://user/preferences/pr-description-chinese",
        "summary": "Use concise structured Chinese for PR descriptions",
    }],
}, sys.stdout)
""",
        encoding="utf-8",
    )
    enabled = temp / "enabled.json"
    enabled.write_text(
        json.dumps(
            {
                "schema_version": "semantic_preference_hook_config_v0",
                "enabled": True,
                "provider": {"argv": [sys.executable, str(provider), str(counter)]},
                "surfaces": {
                    "issue_fix.pr_description": {
                        "query": "PR description preferences",
                        "failure_policy": "fail_open",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    applied = build_issue_fix_pr_description(
        BASE,
        project=project,
        semantic_preference_config=enabled,
        application_id="pr-17-description",
        artifact_ref="https://example.com/pr/17",
        apply_preferences=lambda _base, items: {
            "description": "## 动机\n\n修复已复现的问题。\n",
            "applied_preference_refs": [items[0]["preference_ref"]],
        },
    )
    assert counter.read_text() == "1", "enabled build must call provider once"
    assert applied["description"].startswith("## 动机"), applied
    preference = applied["semantic_preference"]
    assert preference["application_status"] == "applied", preference
    assert preference["receipt"]["outcome"] == "applied", preference
    assert PREFERENCE_REF not in json.dumps(applied), applied

    disabled = temp / "disabled.json"
    disabled.write_text(
        json.dumps(
            {
                "schema_version": "semantic_preference_hook_config_v0",
                "enabled": False,
                "provider": {"argv": [sys.executable, str(provider), str(counter)]},
            }
        ),
        encoding="utf-8",
    )
    disabled_result = build_issue_fix_pr_description(
        BASE,
        project=project,
        semantic_preference_config=disabled,
        apply_preferences=lambda *_: (_ for _ in ()).throw(
            AssertionError("disabled preference must not run the applier")
        ),
    )
    assert counter.read_text() == "1", "disabled build must not call provider"
    assert disabled_result["description"] == BASE, disabled_result
    assert disabled_result["semantic_preference"]["recall_status"] == "disabled"

    def unexpected_recall(*_args, **_kwargs):
        raise AssertionError("unconfigured build must not call recall")

    unconfigured = build_issue_fix_pr_description(
        BASE,
        project=project,
        recall_fn=unexpected_recall,
    )
    assert unconfigured["description"] == BASE, unconfigured

    failing = temp / "failing.json"
    failing.write_text(
        json.dumps(
            {
                "schema_version": "semantic_preference_hook_config_v0",
                "enabled": True,
                "provider": {"argv": [sys.executable, "-c", "raise SystemExit(7)"]},
                "surfaces": {
                    "issue_fix.pr_description": {
                        "query": "PR description preferences",
                        "failure_policy": "fail_open",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    unavailable = build_issue_fix_pr_description(
        BASE,
        project=project,
        semantic_preference_config=failing,
        apply_preferences=lambda *_: (_ for _ in ()).throw(
            AssertionError("unavailable preference must not run the applier")
        ),
    )
    assert unavailable["description"] == BASE, unavailable
    assert unavailable["fail_open_preserved_base"] is True, unavailable

    unattributed = build_issue_fix_pr_description(
        BASE,
        project=project,
        semantic_preference_config=enabled,
        application_id="pr-18-description",
        apply_preferences=lambda *_: {
            "description": "mutated without preference attribution",
            "applied_preference_refs": [],
        },
    )
    assert counter.read_text() == "2", "each enabled build has a one-call budget"
    assert unattributed["description"] == BASE, unattributed
    assert unattributed["semantic_preference"]["receipt"]["outcome"] == "failed"

print("issue-fix PR description builder smoke: ok")
