from __future__ import annotations

import json
from pathlib import Path

from app.core.extensions import Extensions


def test_extensions_load_and_call(scratch_dir: Path) -> None:
    skills_dir = scratch_dir / "skills"
    plugins_dir = scratch_dir / "plugins"
    skills_dir.mkdir(parents=True, exist_ok=True)
    plugins_dir.mkdir(parents=True, exist_ok=True)

    (skills_dir / "s1.toml").write_text(
        'id = "s1"\n'
        'name = "Skill 1"\n'
        "[prompts]\n"
        'profile_agent.system = "SYSTEM_1"\n'
        'profile_agent.user_template = "USER:{text}"\n',
        encoding="utf-8",
    )

    pdir = plugins_dir / "p1"
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "plugin.json").write_text(
        json.dumps(
            {
                "id": "p1",
                "name": "Plugin 1",
                "tools": [{"name": "hello", "entrypoint": "main.py:hello"}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (pdir / "main.py").write_text(
        "from __future__ import annotations\n"
        "\n"
        "def hello(*, name: str) -> dict[str, str]:\n"
        '    return {"msg": f"hi {name}"}\n',
        encoding="utf-8",
    )

    (skills_dir / "doc.SKILL.md").write_text(
        "---\n"
        "name: doc-skill\n"
        'description: "doc"\n'
        "---\n"
        "\n"
        "# Doc\n"
        "hello\n",
        encoding="utf-8",
    )

    ext = Extensions(
        skills_dir=str(skills_dir),
        plugins_dir=str(plugins_dir),
        active_skills=["s1"],
        include_project_root=False,
    )
    assert ext.get_prompt("profile_agent.system") == "SYSTEM_1"
    assert ext.get_prompt("profile_agent.user_template") == "USER:{text}"
    assert ext.call_tool(plugin_id="p1", tool_name="hello", args={"name": "bob"}) == {"msg": "hi bob"}
    assert any(s.skill_id == "doc-skill" and s.kind == "document" for s in ext.list_skills())
