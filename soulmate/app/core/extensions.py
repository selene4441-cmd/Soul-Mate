from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import sys
import threading
import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

from app.core.config import settings


def _project_root() -> Path:
    # app/core/extensions.py -> app/core -> app -> repo root
    return Path(__file__).resolve().parents[2]


def _resolve_dir(path: str) -> Path:
    p = Path(path)
    if p.is_absolute():
        return p
    return _project_root() / p


def _split_csv(value: str) -> list[str]:
    items = [x.strip() for x in (value or "").split(",")]
    return [x for x in items if x]


@dataclass(frozen=True)
class SkillSpec:
    skill_id: str
    name: str
    description: str
    prompts: dict[str, str]
    source_path: str
    kind: str = "prompt"


@dataclass(frozen=True)
class PluginToolSpec:
    name: str
    description: str
    entrypoint: str


@dataclass(frozen=True)
class PluginSpec:
    plugin_id: str
    name: str
    description: str
    tools: list[PluginToolSpec]
    source_path: str


class ExtensionError(RuntimeError):
    pass


class Extensions:
    """
    Loads "skills" (prompt overrides) and "plugins" (callable tools) from disk.

    - Skills directory: `*.toml` files with optional `[prompts]` table.
    - Plugins directory: `<plugin_id>/plugin.json` with `tools[*].entrypoint`.
    """

    def __init__(
        self,
        *,
        skills_dir: str,
        plugins_dir: str,
        active_skills: list[str] | None = None,
        include_project_root: bool = True,
    ) -> None:
        self._skills_dir = _resolve_dir(skills_dir)
        self._plugins_dir = _resolve_dir(plugins_dir)
        self._active_skills = active_skills or []
        self._include_project_root = include_project_root

        self._lock = threading.RLock()
        self._skills: dict[str, SkillSpec] = {}
        self._plugins: dict[str, PluginSpec] = {}
        self._tool_cache: dict[tuple[str, str], Callable[..., Any]] = {}

        self.reload()

    @classmethod
    def from_settings(cls) -> Extensions:
        return cls(
            skills_dir=settings.skills_dir,
            plugins_dir=settings.plugins_dir,
            active_skills=_split_csv(settings.active_skills),
            include_project_root=True,
        )

    def set_active_skills(self, skill_ids: list[str]) -> None:
        with self._lock:
            self._active_skills = list(skill_ids)

    def reload(self) -> None:
        with self._lock:
            self._skills = self._load_skills()
            self._plugins = self._load_plugins()
            self._tool_cache.clear()

    def list_skills(self) -> list[SkillSpec]:
        with self._lock:
            return [self._skills[k] for k in sorted(self._skills)]

    def list_plugins(self) -> list[PluginSpec]:
        with self._lock:
            return [self._plugins[k] for k in sorted(self._plugins)]

    def get_prompt(self, key: str) -> str | None:
        """
        Returns prompt override for `key`, resolved in active skill order.
        Later skills override earlier ones.
        """
        with self._lock:
            for sid in self._active_skills:
                spec = self._skills.get(sid)
                if not spec:
                    continue
                val = spec.prompts.get(key)
                if isinstance(val, str) and val.strip():
                    return val
        return None

    def read_skill_content(
        self,
        *,
        skill_id: str,
        offset: int = 0,
        limit: int = 2000,
    ) -> dict[str, int | str]:
        if offset < 0:
            raise ExtensionError("offset must be >= 0")
        if limit <= 0:
            raise ExtensionError("limit must be > 0")
        if limit > 20000:
            raise ExtensionError("limit too large (max 20000 chars)")

        with self._lock:
            spec = self._skills.get(skill_id)
            if spec is None:
                raise ExtensionError(f"skill not found: {skill_id}")
            path = Path(spec.source_path)
            if not path.exists():
                raise ExtensionError("skill source file missing")

        text = path.read_text(encoding="utf-8", errors="replace")
        total = len(text)
        start = min(offset, total)
        end = min(start + limit, total)
        return {"skill_id": skill_id, "offset": start, "limit": limit, "total": total, "content": text[start:end]}

    def call_tool(self, *, plugin_id: str, tool_name: str, args: dict[str, Any] | None = None) -> Any:
        with self._lock:
            plugin = self._plugins.get(plugin_id)
            if plugin is None:
                raise ExtensionError(f"plugin not found: {plugin_id}")
            tool = next((t for t in plugin.tools if t.name == tool_name), None)
            if tool is None:
                raise ExtensionError(f"tool not found: {plugin_id}.{tool_name}")

            cache_key = (plugin_id, tool_name)
            fn = self._tool_cache.get(cache_key)
            if fn is None:
                fn = self._load_entrypoint(plugin, tool)
                self._tool_cache[cache_key] = fn

        payload = args or {}
        if not isinstance(payload, dict):
            raise ExtensionError("args must be an object")
        try:
            return fn(**payload)
        except TypeError as e:
            raise ExtensionError(f"tool call failed: {e}") from e

    def _load_skills(self) -> dict[str, SkillSpec]:
        search_dirs: list[Path] = []
        if self._skills_dir.exists():
            if not self._skills_dir.is_dir():
                raise ExtensionError(f"skills_dir is not a directory: {self._skills_dir}")
            search_dirs.append(self._skills_dir)
        if self._include_project_root:
            root = _project_root()
            if root not in search_dirs:
                search_dirs.append(root)

        out: dict[str, SkillSpec] = {}
        for base in search_dirs:
            # Prompt skills (toml)
            for path in sorted(base.glob("*.toml")):
                data = tomllib.loads(path.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    continue
                skill_id = str(data.get("id") or path.stem).strip()
                if not skill_id:
                    continue
                name = str(data.get("name") or skill_id).strip()
                description = str(data.get("description") or "").strip()
                prompts_raw = data.get("prompts") or {}
                prompts: dict[str, str] = {}

                def flatten(prefix: str, obj: Any, *, out_map: dict[str, str]) -> None:
                    if not isinstance(obj, dict):
                        return
                    for k, v in obj.items():
                        if not isinstance(k, str):
                            continue
                        full = f"{prefix}{k}" if not prefix else f"{prefix}.{k}"
                        if isinstance(v, str):
                            out_map[full] = v
                        elif isinstance(v, dict):
                            flatten(full, v, out_map=out_map)

                flatten("", prompts_raw, out_map=prompts)
                out[skill_id] = SkillSpec(
                    skill_id=skill_id,
                    name=name,
                    description=description,
                    prompts=prompts,
                    source_path=str(path),
                    kind="prompt",
                )

            # Document skills (SKILL.md)
            for path in sorted(base.glob("*.SKILL.md")):
                spec = self._parse_skill_md(path)
                out[spec.skill_id] = spec
        return out

    def _parse_skill_md(self, path: Path) -> SkillSpec:
        """
        Minimal front-matter parser for `*.SKILL.md`.

        Expected:
        ---
        name: <id>
        description: <text>
        ---
        """
        text = path.read_text(encoding="utf-8", errors="replace")
        skill_id = path.stem.replace(".SKILL", "").strip()
        name = skill_id
        description = ""

        if text.startswith("---"):
            parts = text.split("\n---", 1)
            fm = parts[0]
            # normalize: drop leading '---' line
            fm_lines = [ln for ln in fm.splitlines() if ln.strip() != "---"]
            fm_text = "\n".join(fm_lines)

            import re

            m_name = re.search(r"^name:\s*(.+?)\s*$", fm_text, re.MULTILINE)
            if m_name:
                name = m_name.group(1).strip().strip('"').strip("'")
                skill_id = name
            m_desc = re.search(r"^description:\s*(.+?)\s*$", fm_text, re.MULTILINE)
            if m_desc:
                description = m_desc.group(1).strip().strip('"').strip("'")

        if not skill_id:
            raise ExtensionError(f"invalid skill id for {path}")
        return SkillSpec(
            skill_id=skill_id,
            name=name or skill_id,
            description=description,
            prompts={},
            source_path=str(path),
            kind="document",
        )

    def _load_plugins(self) -> dict[str, PluginSpec]:
        if not self._plugins_dir.exists():
            return {}
        if not self._plugins_dir.is_dir():
            raise ExtensionError(f"plugins_dir is not a directory: {self._plugins_dir}")

        out: dict[str, PluginSpec] = {}
        for plugin_dir in sorted([p for p in self._plugins_dir.iterdir() if p.is_dir()]):
            manifest = plugin_dir / "plugin.json"
            if not manifest.exists():
                continue
            data = json.loads(manifest.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                continue
            plugin_id = str(data.get("id") or plugin_dir.name).strip()
            if not plugin_id:
                continue
            name = str(data.get("name") or plugin_id).strip()
            description = str(data.get("description") or "").strip()
            tools_raw = data.get("tools") or []
            tools: list[PluginToolSpec] = []
            if isinstance(tools_raw, list):
                for t in tools_raw:
                    if not isinstance(t, dict):
                        continue
                    t_name = str(t.get("name") or "").strip()
                    t_desc = str(t.get("description") or "").strip()
                    t_entry = str(t.get("entrypoint") or "").strip()
                    if not t_name or not t_entry:
                        continue
                    tools.append(PluginToolSpec(name=t_name, description=t_desc, entrypoint=t_entry))
            out[plugin_id] = PluginSpec(
                plugin_id=plugin_id,
                name=name,
                description=description,
                tools=tools,
                source_path=str(manifest),
            )
        return out

    def _load_entrypoint(self, plugin: PluginSpec, tool: PluginToolSpec) -> Callable[..., Any]:
        """
        Entrypoint format:
        - "main.py:fn" (file relative to plugin directory)
        - "pkg.module:fn" (importable module)
        """
        if ":" not in tool.entrypoint:
            raise ExtensionError(f"invalid entrypoint (missing ':'): {tool.entrypoint}")
        left, right = tool.entrypoint.split(":", 1)
        module_ref = left.strip()
        attr_name = right.strip()
        if not module_ref or not attr_name:
            raise ExtensionError(f"invalid entrypoint: {tool.entrypoint}")

        module: ModuleType
        if module_ref.endswith(".py") or "/" in module_ref or "\\" in module_ref:
            plugin_dir = Path(plugin.source_path).resolve().parent
            file_path = (plugin_dir / module_ref).resolve()
            try:
                if not file_path.is_relative_to(plugin_dir):
                    raise ExtensionError("entrypoint must stay within plugin directory")
            except AttributeError:
                # Python <3.9 fallback (not expected in this project, but kept for safety)
                if not str(file_path).startswith(str(plugin_dir)):
                    raise ExtensionError("entrypoint must stay within plugin directory")
            if not file_path.exists():
                raise ExtensionError(f"entrypoint file not found: {file_path}")
            module = self._import_module_from_file(file_path, module_name=f"soulmate_plugin_{plugin.plugin_id}")
        else:
            module = importlib.import_module(module_ref)

        fn = getattr(module, attr_name, None)
        if not callable(fn):
            raise ExtensionError(f"entrypoint is not callable: {tool.entrypoint}")
        return fn  # type: ignore[return-value]

    def _import_module_from_file(self, file_path: Path, *, module_name: str) -> ModuleType:
        digest = hashlib.sha256(str(file_path).encode("utf-8")).hexdigest()[:16]
        mod_name = f"{module_name}_{digest}"
        if mod_name in sys.modules:
            return sys.modules[mod_name]

        spec = importlib.util.spec_from_file_location(mod_name, file_path)
        if spec is None or spec.loader is None:
            raise ExtensionError(f"failed to load module: {file_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = module
        spec.loader.exec_module(module)
        return module


extensions = Extensions.from_settings()
