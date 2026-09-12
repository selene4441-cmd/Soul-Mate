import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEVCONTAINER = ROOT / ".devcontainer"


def test_codespaces_configuration_starts_and_forwards_the_web_app():
    config = json.loads((DEVCONTAINER / "devcontainer.json").read_text(encoding="utf-8"))
    assert config["forwardPorts"] == [3000]
    assert "setup.sh" in config["postCreateCommand"]
    assert "start.sh" in config["postStartCommand"]
    assert config["portsAttributes"]["3000"]["onAutoForward"] == "openPreview"


def test_codespace_setup_installs_runs_migrations_and_links_workspace():
    setup = (DEVCONTAINER / "setup.sh").read_text(encoding="utf-8")
    assert "python -m venv .venv" in setup
    assert "pip install -r requirements.txt" in setup
    assert "alembic upgrade head" in setup
    assert "pnpm install --frozen-lockfile" in setup


def test_codespace_start_launches_api_and_web_without_copying_scores():
    start = (DEVCONTAINER / "start.sh").read_text(encoding="utf-8")
    assert "uvicorn app.main:app" in start
    assert "pnpm --filter tongpin-web dev" in start
    assert "127.0.0.1:8000/api/v1/health" in start
    assert "127.0.0.1:3000" in start
    assert "ranking_score" not in start
    assert "success_probability" not in start


def test_readme_has_codespaces_badge_and_local_launchers():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    docs = (ROOT / "docs" / "github-usage.md").read_text(encoding="utf-8")
    assert "codespaces.new/selene4441-cmd/Soul-Mate" in readme
    assert "start-local.ps1" in readme
    assert "start-local.sh" in readme
    assert "GitHub Pages" in docs
    assert "每一个同伴打开自己的 Codespace" in docs


def test_shell_scripts_are_valid_when_bash_is_available():
    bash = shutil.which("bash")
    if bash is None:
        return
    for script in (
        DEVCONTAINER / "setup.sh",
        DEVCONTAINER / "start.sh",
        ROOT / "scripts" / "start-local.sh",
    ):
        result = subprocess.run(
            [bash, "-n", str(script)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
