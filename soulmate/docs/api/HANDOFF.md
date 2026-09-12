# 交接说明：SoulMate Agent 后端 → 前端

> 面向"怎么把这套东西交出去"。读完你会得到：**交付物清单、三种交付渠道、一段可以直接复制给前端的话、验收标准、边界约定**。

---

## 一、你要交付的四样东西

| # | 交付物 | 位置 | 没有它会怎样 |
|---|---|---|---|
| 1 | **接口契约**（人读 + 机器可读 + 类型） | `docs/api/` + `web/lib/api/` | 前端靠猜字段名，返工率极高 |
| 2 | **可运行的演示数据** | `scripts/seed_demo.py` | 前端要手工注册 5 个账号、互相邀请、造聊天记录，第一小时全花在这上面 |
| 3 | **可执行的自检脚本** | `scripts/smoke_e2e.py` | "什么叫验收通过"没有客观定义，只能靠嘴对 |
| 4 | **后端访问方式**（仓库权限 或 运行环境） | 见渠道选择 | 前端只能对着契约写，无法联调 |

> 关键认知：**只给契约 = 一定返工**。给出 1+2+3 之后，前端在你不在场的情况下也能自己跑通全流程。

---

## 二、三种交付渠道，按前端的位置选

### 渠道 A：前端能用同一个仓库（最推荐）

给仓库访问权（GitHub 加 collaborator，或内网 Git），然后他只需要三条命令：

```bash
git clone <repo> && cd SoulMate/soulmate
python -m alembic upgrade head
python -m scripts.seed_demo --reset
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

再开一个终端跑自检，确认环境没问题：

```bash
python -m scripts.smoke_e2e      # 期望输出「结论: 全部通过」
```

**适合**：同一个团队 / 能开权限。契约随代码演进，前端不会拿到过期版本。

### 渠道 B：前端在外部（外包、别的公司、不能给仓库）

打包一个自包含 zip 给他。包内结构：

```
soulmate-frontend-handoff/
  README-交接.md          <- 这份文件
  api/API-CONTRACT.md     <- 人读契约（主文档）
  api/openapi.yaml        <- 导入 Postman/Apifox，或用 Prism 起 mock
  api/README.md           <- 契约包说明
  api/tools/*.py          <- 契约自检脚本
  web-lib/api/types.ts    <- 直接放进他的 lib/ 即可
  web-lib/api/client.ts
  scripts/seed_demo.py    <- 需要后端代码才能跑（可选给）
  scripts/smoke_e2e.py
```

打不出来后端环境也没关系——直接告诉他用 Prism 起 mock：

```bash
npx @stoplight/prism-cli mock api/openapi.yaml --port 4010
```

**必须额外叮嘱外部前端两件事**（否则他一定会踩）：
1. 浏览器**不能**直连后端（无 CORS + `SameSite=Lax`），必须走同源代理，代码在契约第 1.3 节。
2. 写操作必须带 `X-CSRF-Token`（值取 cookie `tongpin_csrf`），`client.ts` 已封装。

### 渠道 C：只发一份文档

不推荐，但如果是"先对齐设计、暂不写代码"，可以只发 `API-CONTRACT.md` + `openapi.yaml`，
并且**明确告诉他哪些是已实现、哪些是 planned**（契约里已用 `x-contract-status` 标好）。

---

## 三、可以直接复制给前端的话

> 你好，SoulMate Agent 的后端接口已经整理好交接给你，基准是提交 `e2d2401`（后续可能更新，以仓库里的 `docs/api/` 为准）。
>
> **先看两个文件**：`docs/api/README.md`（一页纸）→ `docs/api/API-CONTRACT.md`（完整契约）。
> 类型和客户端直接用 `web/lib/api/types.ts`、`web/lib/api/client.ts`，不要自己手写类型。
> 接口的机器可读版本是 `docs/api/openapi.yaml`，可以导入 Apifox/Postman，也可以 `npx @stoplight/prism-cli mock` 起 mock 先写 UI。
>
> **三条必须先知道的事**：
> 1. 浏览器不能直连后端（后端没有 CORS，cookie 是 `SameSite=Lax`）。所有请求走同源代理 `/api/proxy/v1/*`，代理代码在契约 1.3 节，直接复制就能用。
> 2. 所有 POST/PATCH/DELETE 必须带 `X-CSRF-Token`，值等于 cookie `tongpin_csrf`；`client.ts` 已经自动处理。
> 3. **界面上不允许出现匹配度、百分比、排名、等级、人格报告、MBTI、用户标签、用户画像**。后端响应里也刻意没有这些字段。推荐理由要用「共同点 / 差异 / 还不确定」三块展示，其中「还不确定」必须显示出来。
>
> **联调方式**（两条命令，我会把仓库权限给你）：
> ```
> python -m alembic upgrade head
> python -m scripts.seed_demo --reset
> python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
> ```
> 演示账号密码统一 `password123`，五个账号正好覆盖四种界面状态：
> - `demo1@example.com`（林屿）→ 推荐列表页
> - `demo2@example.com`（苏晚）→ 聊天页（已有 4 条历史消息）
> - `demo3@example.com`（周聿）→ 「Your Story + 看看可能的人」页
> - `demo4@example.com`（何枝）→ 问卷引导页
> 前端路由**只依据** `GET /api/v1/space/state` 的 `state` 字段，不要自己推断。
>
> **自检**：写完一个阶段跑 `python -m scripts.smoke_e2e`，它会检查 CSRF、幂等、WebSocket、以及"响应里不能有分数字段"。它同时也是验收标准的可执行定义。
>
> **改动规则**：`docs/api/` 和 `web/lib/api/` 下的文件不要直接改，需要调整接口请在群里说（或提 PR 描述需求），我改后端 + 同步契约；否则两边会漂移。
>
> 契约里标了 `x-contract-status: planned` 的 10 个接口（猜测卡、信念、匹配叙事等）**能力已实现但还没搬到 `/api/v1`，暂时不要依赖**，我会在迁移完成后通知你。

---

## 四、验收标准（前端交付时你怎么检查）

| 层级 | 检查项 | 通过标准 |
|---|---|---|
| 环境 | `python -m scripts.smoke_e2e` | 输出「结论: 全部通过」 |
| 接入 | 用同源代理调 `GET /api/v1/auth/me` | 未登录返回 401 且被前端正确识别；登录后返回用户 |
| CSRF | 故意去掉 `X-CSRF-Token` 发 POST | 前端不把 `CSRF_INVALID` 弹给用户（这是前端 bug 不是用户错误） |
| 状态机 | 用五个演示账号逐个登录 | 四个主账号分别落到 MATCHING / CHAT / SELF_PROFILE_READY / EXPLORING，与契约 7.0 表格一致 |
| 幂等 | 断网重试发消息（同 `client_message_id`） | 不产生重复气泡 |
| 实时 | 两个浏览器分别登录「苏晚」「温野」 | 一边发消息另一边实时出现，且不重复渲染 |
| **红线** | 全站搜关键词 | 无「匹配度/百分比/排名/等级/人格报告/MBTI/标签/画像」；无进度条式打分 |
| 诚实感 | 推荐卡片 | 「还不确定」区块有渲染，没有被隐藏或折叠 |
| 降级 | 401 / 403 / 429 / 500 | 四种错误都有明确 UI（429 要退避重试，401 跳登录，403+`CONSENT_REQUIRED` 弹授权说明） |

红线那条建议直接做成 CI 检查或提交前 grep，别靠人眼。

---

## 五、边界约定（先说清楚，省掉后面扯皮）

| 谁 | 负责 | 不碰 |
|---|---|---|
| 你（后端） | `/api/v1/*` 的行为、`docs/api/` 契约、演示数据、迁移 planned 接口 | 前端组件与样式 |
| 前端 | 页面、状态机消费、错误态、红线自查、同源代理 | `docs/api/`、`web/lib/api/` 的契约文件 |
| 共同 | 契约变更走"先改契约 → 双方确认 → 各自实现" | 谁都不能单方面改字段名 |

**契约变更流程**（一句话）：任何字段增删改，先由需要方在群里提出 → 我改 `openapi.yaml` + 文档 → 重新跑 `docs/api/tools/validate-openapi.py` → 通知前端。

---

## 六、前端可以立刻开始的三件事（不用等你）

1. 用 `openapi.yaml` 起 Prism mock，把四个状态的页面骨架和路由搭出来（`space/state` 的四种 state 都有 mock 数据）。
2. 按契约 1.3 节把同源代理 Route Handler 写好，并用 `GET /api/v1/auth/me` 打通登录态探测。
3. 把红线词清单接进 lint/CI。

这三件都不依赖后端迁移 `planned` 的那 10 个接口。

---

## 七、你还需要补的两件事（按优先级）

1. **把 10 个 planned 接口迁到 `/api/v1/me/*` 并加 session 鉴权** —— 迁移完前端才能用到信息熵那套玩法（猜测卡 → 作答 → 信念可视化）。
   现状风险：这些接口挂在旧根路径且**无鉴权**，任何人知道 user_id 就能读他人 profile/belief/story。
2. **给后端加 CORS 或确认只走同源代理** —— 如果最终是前端与后端分域部署（不同域名），现在是必然连不通的，需要 `CORSMiddleware(allow_credentials=True)` + `SameSite=None; Secure`（要求 HTTPS）。
