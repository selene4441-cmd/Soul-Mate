from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / ".agents" / "skills" / "tongpin"


def test_skill_frontmatter_and_scope_are_complete():
    text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    assert text.startswith("---\n")
    frontmatter = text.split("---", 2)[1]
    assert "name: tongpin" in frontmatter
    assert "Tongpin/同频" in frontmatter
    assert "TODO" not in text


def test_skill_preserves_product_privacy_and_explanation_invariants():
    text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    for required in (
        "consent_scope",
        "ranking_score",
        "success_probability",
        "matching percentage",
        "fixed personality label",
        "safety events",
        "content-free audit tombstone",
    ):
        assert required in text


def test_skill_has_operational_reference_and_ui_metadata():
    reference = (SKILL_DIR / "references" / "operations.md").read_text(encoding="utf-8")
    metadata = (SKILL_DIR / "agents" / "openai.yaml").read_text(encoding="utf-8")
    assert "scripts/start-local.sh" in reference
    assert "start-local.ps1" in reference
    assert "/api/v1/health" in reference
    assert 'display_name: "同频产品助手"' in metadata
    assert "allow_implicit_invocation: true" in metadata


def test_readme_exposes_the_project_skill():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert ".agents/skills/tongpin/SKILL.md" in readme
    assert "$tongpin" in readme
