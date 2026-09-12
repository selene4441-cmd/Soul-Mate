# Soulmate Agent — 项目说明（Codex 必读）

## 目标
基于“隐性信息 + 诱导式交互”的匹配 Agent：从静默行为与用户反馈中构建画像，
降低“是否灵魂伴侣”的不确定性（信息熵），输出匹配分与解释。

## 技术栈
- Python 3.12 + FastAPI + SQLAlchemy 2.x + Alembic + pytest
- 向量检索：MVP 用 SQLite + numpy；后期迁 PostgreSQL + pgvector
- LLM：OpenAI 兼容接口（base_url / model / api_key 从 `.env` 读取）
- 依赖管理：`requirements.txt`；代码风格：ruff + black；类型注解必须写

## 目录约定
`app/{api,agents,models,core}/`  `tests/`  `scripts/`  `data/`  `logs/`  `reports/`

## 硬约束
- 禁止抓取小红书等第三方平台用户数据；开发期只用 `scripts/` 生成的合成数据
- 任何涉及个人信息的功能必须显式同意 + 可删除
- 每个模块必须有单元测试；不写测试不算完成
- 提交信息格式：`feat:` / `fix:` / `test:` / `docs:`

## 常用命令
`pytest -q`  `ruff check .`  `uvicorn app.main:app --reload`
