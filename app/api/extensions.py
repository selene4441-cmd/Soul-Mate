from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.extensions import ExtensionError, extensions

router = APIRouter(prefix="/extensions", tags=["extensions"])


class SkillOut(BaseModel):
    skill_id: str
    name: str
    description: str
    prompts: dict[str, str]
    source_path: str
    kind: str | None = None


class PluginToolOut(BaseModel):
    name: str
    description: str
    entrypoint: str


class PluginOut(BaseModel):
    plugin_id: str
    name: str
    description: str
    tools: list[PluginToolOut]
    source_path: str


class CallToolIn(BaseModel):
    args: dict[str, Any] = Field(default_factory=dict)


@router.get("/skills", response_model=list[SkillOut])
def list_skills() -> list[SkillOut]:
    return [SkillOut(**s.__dict__) for s in extensions.list_skills()]


@router.get("/plugins", response_model=list[PluginOut])
def list_plugins() -> list[PluginOut]:
    out: list[PluginOut] = []
    for p in extensions.list_plugins():
        out.append(
            PluginOut(
                plugin_id=p.plugin_id,
                name=p.name,
                description=p.description,
                tools=[PluginToolOut(**t.__dict__) for t in p.tools],
                source_path=p.source_path,
            )
        )
    return out


@router.post("/reload")
def reload_extensions() -> dict[str, int]:
    try:
        extensions.reload()
    except ExtensionError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"skills": len(extensions.list_skills()), "plugins": len(extensions.list_plugins())}


@router.get("/skills/{skill_id}/content")
def get_skill_content(skill_id: str, offset: int = 0, limit: int = 2000) -> dict[str, int | str]:
    try:
        return extensions.read_skill_content(skill_id=skill_id, offset=offset, limit=limit)
    except ExtensionError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/plugins/{plugin_id}/tools/{tool_name}")
def call_tool(plugin_id: str, tool_name: str, payload: CallToolIn) -> dict[str, Any]:
    try:
        result = extensions.call_tool(plugin_id=plugin_id, tool_name=tool_name, args=payload.args)
    except ExtensionError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"result": result}
