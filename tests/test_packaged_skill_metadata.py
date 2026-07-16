import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_packaged_loopx_skills_use_canonical_brand_display_names() -> None:
    skill_dirs = sorted((REPO_ROOT / "skills").glob("loopx-*"))
    assert skill_dirs

    for skill_dir in skill_dirs:
        metadata_path = skill_dir / "agents" / "openai.yaml"
        assert metadata_path.is_file(), f"{skill_dir.name} must declare an explicit display name"
        metadata = metadata_path.read_text(encoding="utf-8")
        match = re.search(r'^\s*display_name:\s*"([^"]+)"\s*$', metadata, re.MULTILINE)
        assert match, f"{metadata_path} must declare interface.display_name"
        display_name = match.group(1)
        assert display_name == "LoopX" or display_name.startswith("LoopX "), display_name
        assert not display_name.startswith("Loopx"), display_name
