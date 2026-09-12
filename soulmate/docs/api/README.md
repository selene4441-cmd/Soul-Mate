# SoulMate Agent · 前端对接包

一套可以直接交给前端开发的**接口契约**。基准代码：`soulmate` @ commit `e2d2401`（可由 `git log -1` 核对）。

## 文件构成

| 文件 | 定位 | 怎么用 |
|---|---|---|
| `API-CONTRACT.md` | **人读契约**（主文档） | 先读它。接入方式、错误码表、状态机、逐接口、产品红线、联调 checklist 都在里面 |
| `openapi.yaml` | **机器可读契约**（OpenAPI 3.1，25 路径 / 27 操作 / 40 schema） | 导入 Postman/Apifox；或 `npx @stoplight/prism-cli mock openapi.yaml --port 4010` 起 mock，不需要等后端 |
| `../../web/lib/api/types.ts` | **TypeScript 类型**（40+ 类型，`--strict` 通过） | 直接 `import type { ... } from "@/lib/api/types"` |
| `../../web/lib/api/client.ts` | **类型化客户端**（无依赖） | 已封装同源代理、CSRF 双提交、统一错误、WebSocket 去重 |
| `tools/validate-openapi.py` | 契约自检 | `python tools/validate-openapi.py`（校验 YAML 结构 + `$ref` 完整性 + tag 一致性） |
| `tools/lint-yaml-plain.py` | 契约自检 | `python tools/lint-yaml-plain.py openapi.yaml`（抓非法的 YAML 纯量写法） |

## 三条必须先知道的结论

1. **浏览器不能直连后端**。后端没有 CORS 中间件，且 session cookie 是 `SameSite=Lax`。
   前端所有请求走同源代理 `/api/proxy/v1/*`（Route Handler 代码见 `API-CONTRACT.md` 第 1.3 节）。
2. **所有写操作必须带 `X-CSRF-Token`**，值取 JS 可读 cookie `tongpin_csrf`。
   `auth/register` 与 `auth/login` 豁免。`client.ts` 已自动处理。
3. **响应里没有匹配度、百分比、排名、等级** —— 这是产品红线，不是后端漏了。
   前端也不得自行计算或展示（禁止词清单见 `API-CONTRACT.md` 第 6 节与 `types.ts` 末尾常量）。

## 契约里两类接口

- **已实现**（`x-contract-status: implemented`，17 个操作）：现在就能联调，路径就是 `/api/v1/*`。
- **待迁移**（`x-contract-status: planned`，10 个操作）：能力已实现，但当前挂在旧根路径且**无鉴权**，
  每个接口都标了 `x-current-path` 说明它现在在哪。前端迁移完成前不要直接依赖；
  真要临时验证信息熵玩法，请集中包在一个 `legacy-agent.ts` 里并标注 TODO。

## 契约与后端的一致性

`openapi.yaml` 不是手抄的：它由后端真实 `app.openapi()` 导出（31 条路径 / 40 schema）逐条核对生成，
并通过脚本交叉校验过「不漏、不编造、planned 都能追溯到真实路由」。后端改动后请重新校验：

```bash
cd soulmate
python -c "import json;from app.main import app;open('openapi.json','w',encoding='utf-8').write(json.dumps(app.openapi(),ensure_ascii=False,indent=2))"
python docs/api/tools/validate-openapi.py
```

也可以直接打开运行中的服务看实时契约：`http://127.0.0.1:8000/docs`。

## 已知待修（前端可先绕过，不必等）

| # | 问题 | 绕过方式 |
|---|---|---|
| 1 | `GET /api/v1/space/state` 的 `question.options` 恒为空数组 | 用 `GET /api/v1/questionnaire` 取题库，按 `dimension` 匹配 |
| 2 | 429 的 `code` 是通用的 `HTTP_ERROR` | 按 HTTP 状态码 429 判断并退避 |
| 3 | WebSocket `message.created` 缺 `sender_id` / `created_at` | 收到事件后调 `GET /api/v1/matches/{id}/messages` 补全 |
| 4 | Agent 能力（猜测卡/信念/叙事）仍在旧根路径且无鉴权 | 见上「待迁移」说明 |
| 5 | 限流只挂在旧路径的 agent 接口上 | 迁移时需一并带过去 |
