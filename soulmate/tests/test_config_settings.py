from __future__ import annotations

from pathlib import Path

from app.core.config import Settings


def test_settings_extra_ignored(scratch_dir: Path) -> None:
    env_file = scratch_dir / ".env"
    env_file.write_text(
        "DATABASE_URL=sqlite+pysqlite:///./data/test.db\n"
        "OPENAI_EMBEDDING_MODEL=text-embedding-3-small\n"
        "SOME_FUTURE_FLAG=yes\n",
        encoding="utf-8",
    )

    s = Settings(_env_file=str(env_file))
    assert s.database_url.endswith("test.db")
    assert s.openai_embedding_model == "text-embedding-3-small"
