# Soulmate

匹配 Agent（MVP）项目骨架。

## 快速开始

1. 创建并激活虚拟环境：`python -m venv .venv` 然后 `.venv\Scripts\activate`（Windows）
2. 安装依赖：`pip install -r requirements.txt`
3. 复制 `.env.example` 为 `.env` 并填写值
4. 初始化数据库：`python -m alembic upgrade head`
5. 生成合成数据：`python scripts/gen_synthetic.py --users 20 --no-llm`
6. 启动控制台：`python scripts/agent_console.py`

也可以直接运行 `start-soulmate.cmd` 一键启动（后端 + 接口文档 + 控制台）。

控制台菜单 1-7：

1. 数据库概览（各表行数）
2. 生成/刷新用户画像（真实 LLM）
3. 查看用户画像列表
4. 为用户寻找匹配（向量召回 + LLM 重排）
5. 一轮诱导卡片（回答问题 → 信念更新）
6. 完整闭环：探测→反馈→更新→匹配→解释
7. 信念状态（当前会话后验与最近记录）

## Web（Next.js）

前端位于 `web/`，通过 Next.js Route Handler 代理转发到后端 `/events`（避免 CORS）。

1. `cd web`
2. `cp .env.local.example .env.local`（Windows 可手动复制，并确认 `API_BASE_URL`）
3. `npm install`
4. `npm run dev`

## 常用命令

- `pytest -q`
- `ruff check .`
- `uvicorn app.main:app --reload`

## Extensions (Skills & Plugins)

- Skills:
  - Prompt skill: add `*.toml` under `skills/`
  - Document skill: put `*.SKILL.md` under repo root (e.g. `tongpin-all.SKILL.md`) or `skills/`
  - Enable via `ACTIVE_SKILLS=example,other`
- Plugins: add folders under `plugins/<plugin_id>/plugin.json` (see `plugins/example_echo/`).
- API: `GET /extensions/skills`, `GET /extensions/plugins`, `POST /extensions/reload`, `POST /extensions/plugins/{plugin_id}/tools/{tool_name}`.
