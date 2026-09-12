# 同频 Web v0.1

“同频”是一个响应式 Web 关系匹配产品。它不把关系结果压缩成确定性的数字或人格标签，而是把共同点、差异和未知信息放在一起，让用户通过具体相处继续确认。

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/selene4441-cmd/Soul-Mate)

本仓库的产品和数据约束来自：

- `docs/matching-metrics-v0.1.md`
- `docs/web-technical-architecture-v0.1.md`

## 当前交付

- Next.js + TypeScript 响应式用户端
- FastAPI + Pydantic + SQLAlchemy 2 模块化单体 API
- PostgreSQL + pgvector 数据契约和 Alembic 初始迁移
- 同意范围、撤回、Cookie 会话、CSRF、速率限制和安全响应头
- Evidence 与可修正 Claim 生命周期
- 硬约束、安全否决、双人关系信号、探索位置和可追溯解释
- 邀请、站内消息、WebSocket 更新与轮询降级
- 7/14/30 天结果反馈
- 隐私删除、无正文审计墓碑和管理审核接口骨架
- PostgreSQL、Redis、Celery、FastAPI、Next.js 的 Docker Compose 基础设施

## 目录

```text
apps/web/                     Next.js 用户端与管理端页面
services/backend/app/api/     /api/v1 路由与 WebSocket
services/backend/app/modules/ Consent、Claims、Matching、Interaction 等领域模块
services/backend/migrations/  Alembic 迁移
packages/contracts/           生成式客户端预留目录
infra/compose/                本地依赖编排
infra/deploy/                 容器构建文件
tests/                        后端集成、契约和文档回归测试
```

## Codex Skill

仓库根目录提供自包含单文件 [`tongpin.skill.md`](tongpin.skill.md)，适合直接分享；Codex 自动发现所需的标准技能目录是 [`.agents/skills/tongpin/SKILL.md`](.agents/skills/tongpin/SKILL.md)。在仓库中打开 Codex 后，可以显式调用：

```text
$tongpin 启动同频并带我走完一次完整流程
```

技能会先定位仓库，再按用户目标选择启动、演示、检查或验证模式。它不会把产品简化成文档问答，而是操作真实的 FastAPI、Next.js、SQLite/PostgreSQL 和测试流程，并强制保留同意、隐私、安全否决和无确定性标签等产品约束。

详细操作步骤位于 [`.agents/skills/tongpin/references/operations.md`](.agents/skills/tongpin/references/operations.md)。如果要把技能安装到个人 Codex 技能目录，可复制整个 `.agents/skills/tongpin` 文件夹到 `$CODEX_HOME/skills/`；在仓库外调用时，技能会要求提供本地仓库路径。
## 在 GitHub 中一键使用

推荐使用 GitHub Codespaces：点击仓库顶部 README 的 **Open in GitHub Codespaces**，等待环境初始化完成，然后打开自动转发的 `3000` 端口。

每个 Codespace 都拥有独立的 SQLite 数据库和本地种子候选人，适合同伴立即体验完整流程。它不会自动与访问你仓库的其他人共享数据；如果希望多人访问同一套数据，需要把 Docker Compose 部署到一台持续运行的云主机、容器平台或内网服务器。

也可以在本机用一条命令启动前后端：

```powershell
# Windows
powershell -ExecutionPolicy Bypass -File .\scripts\start-local.ps1
```

```bash
# macOS / Linux / Git Bash
bash scripts/start-local.sh
```

脚本会创建虚拟环境、安装依赖、执行迁移，并启动 `http://127.0.0.1:3000`。详细说明见 `docs/github-usage.md`。
## 本地运行

需要 Python 3.12、Node.js 22+ 和 pnpm 11。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env

# 初始化本地 SQLite（仅开发默认值）
alembic upgrade head

# 终端 1：API
$env:PYTHONPATH = "services/backend"
uvicorn app.main:app --reload --port 8000

# 终端 2：Web
pnpm install
pnpm dev
```

访问 `http://localhost:3000`。OpenAPI 文档位于 `http://localhost:8000/docs`。

生产与预发布默认使用 PostgreSQL；SQLite 只用于无依赖的本地开发和测试。切换数据库由 `DATABASE_URL` 控制，结构变更统一通过 Alembic。

## 授权与隐私边界

数据只有在对应 `consent_scope` 有效时才进入匹配链路：

- `matching:v1`：读取确认后的 Claim，生成关系线索。
- `conversation:v1`：在双方同意后保存站内消息。
- `outcomes:v1`：记录关系结果反馈。

原始内容与最终排序隔离。浏览器的推荐 DTO 只包含共同点、差异、未知项和继续了解建议，不包含 `ranking_score`、`success_probability`、`confidence` 或原始解释因素。

## 验证

```powershell
# 后端：单元、集成、隐私、契约、迁移结构
python -m pytest -q

# 前端：类型、UI 文案红线、生产构建
pnpm --filter tongpin-web typecheck
pnpm --filter tongpin-web test
pnpm --filter tongpin-web build

# 迁移可从空数据库升级
alembic upgrade head
```

UI 回归测试会阻止匹配百分比、星级、等级、固定人格标签和确定性措辞重新进入产品界面。

## 接入已有后端框架

如果同伴已经准备好自己的后端框架，推荐让它作为同源网关反向代理 `/api/v1`，并保留 Cookie、CSRF、幂等键和 WebSocket Upgrade。不要复制同频的 Claim、匹配或安全规则，也不要直接连接同频数据库。

- 接入方案、Express 与 Spring Cloud Gateway 示例：`docs/backend-integration.md`
- Nginx 配置样例：`infra/nginx/tongpin.conf`
- API 契约：`packages/contracts/openapi.json`

当前版本尚未提供服务账号/API Key 模式。如果同伴要让自有用户体系从服务端直接调用，而不是做网关或用户会话代理，需要先补一份独立的服务间认证契约。

## Docker Compose

```powershell
docker compose -f infra/compose/docker-compose.yml up --build
```

Compose 会启动 PostgreSQL + pgvector、Redis、FastAPI、Celery Worker 和 Next.js。

## v0.1 限制

- 短信、邮件、Web Push 和对象存储签名下载尚未接入真实供应商。
- “首批候选人”由本地种子数据模拟；生产召回必须替换为真实用户池与经过评审的 Embedding 方案。
- 管理端只提供安全事件和版本查看骨架，RBAC 与不可篡改审计需接入生产身份系统。
- 法律、个人信息保护、推荐算法和数据驻留要求仍需在上线前完成正式评审。