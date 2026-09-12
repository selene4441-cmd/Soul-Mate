# 00 · 先读我（操作说明）

这是 SoulMate Agent 的后端接口交接包。**照着下面走一遍，你就能在不问我任何问题的情况下跑通全流程。**

- 契约基准：`soulmate` @ commit `3ddff2a`
- 包内所有接口字段都取自后端真实代码，没有臆造
- 有任何对不上的地方，请按第 9 节的方式反馈（带上 `trace_id`）

---

## 1. 这个包里有什么，谁该读哪一份

| 文件 | 用途 | 谁读 |
|---|---|---|
| `00-START-HERE-操作说明.md` | 本文件，上手与排查 | **你（前端）** |
| `01-交接说明-给后端负责人.md` | 交付渠道、验收标准、改动规则 | 后端负责人 |
| `api/API-CONTRACT.md` | **完整契约**：接入方式、错误码、状态机、逐接口、产品红线、联调 checklist | 你 |
| `api/openapi.yaml` | 机器可读契约（OpenAPI 3.1） | 导入 Apifox/Postman，或起 mock |
| `api/README.md` | 契约包索引 | 参考 |
| `api/tools/validate-openapi.py` | 契约自检（结构 + `$ref`） | 参考 |
| `api/tools/lint-yaml-plain.py` | 契约自检（YAML 语法） | 参考 |
| `web-lib/api/types.ts` | **TypeScript 类型**，直接放进你的项目 | **你** |
| `web-lib/api/client.ts` | **类型化客户端**（封装代理/CSRF/错误/WS） | **你** |
| `web-lib/proxy-route.ts` | 同源代理的现成实现 | **你** |
| `scripts/seed_demo.py` | 生成 5 个演示账号（覆盖四种界面状态） | 你（需要后端代码） |
| `scripts/smoke_e2e.py` | 17 项链路自检＝可执行的验收标准 | 你 |
| `scripts/check-redlines.mjs` | 红线词自查，接进 CI | 你 |

**建议阅读顺序**：本文件 → `api/API-CONTRACT.md` 第 1、2、3 节（接入/错误/状态机）→ 需要哪个接口再翻第 5 节。

---

## 2. 三条路径，按你的情况选一条

| 路径 | 你的情况 | 走第几节 |
|---|---|---|
| **A** | 能拿到后端代码、能跑 Python | 第 3 节（**推荐**，联调最真实） |
| **B** | 只有这个包，拿不到后端 | 第 4 节（用 Prism 起 mock，UI 可以全部先写完） |
| **C** | 现在只想看看接口长什么样 | 第 5 节 |

三条路径的共同前提：**必须做同源代理**（第 6 节），否则浏览器连不上后端。

---

## 3. 路径 A：本地起真后端（推荐）

### 3.1 起服务

```powershell
cd <你的路径>\SoulMate\soulmate
python -m alembic upgrade head              # 首次建表，之后可跳过
python -m scripts.seed_demo --reset         # 生成演示数据
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

看到 `Uvicorn running on http://127.0.0.1:8000` 即成功。另开一个终端：

```powershell
cd <你的路径>\SoulMate\soulmate
python -m scripts.smoke_e2e
```

**期望输出最后一行：`结论: 全部通过`**（前面会有 17 个 `[OK  ]`）。
如果这里是失败，说明环境有问题，先解决它再写前端。

### 3.2 五个演示账号（密码统一 `password123`）

这四个账号**正好分别对应四种界面状态**，切账号就能把四个页面全看到：

| 账号 | 邮箱 | 登录后应看到 | 用来做什么 |
|---|---|---|---|
| 林屿 | `demo1@example.com` | **MATCHING** | 推荐列表页：卡片含「共同点/差异/还不确定」 |
| 苏晚 | `demo2@example.com` | **CHAT** | 聊天页：已有 4 条历史消息 |
| 周聿 | `demo3@example.com` | **SELF_PROFILE_READY** | Your Story 页 +「看看可能的人」按钮 |
| 何枝 | `demo4@example.com` | **EXPLORING** | 问卷引导页（故意没答题） |
| 温野 | `demo5@example.com` | CHAT | 配套账号：和苏晚一对一聊天用 |

> 判据只看 `GET /api/v1/space/state` 的 `state` 字段，**不要自己推断**。
> 四个状态的含义与对应界面见 `api/API-CONTRACT.md` 第 3 节。

### 3.3 交互式文档

浏览器打开 `http://127.0.0.1:8000/docs`，可以在页面上直接调接口试字段。

---

## 4. 路径 B：没有后端，用 mock 写 UI

```bash
npx @stoplight/prism-cli mock api/openapi.yaml --port 4010
```

mock 会按 `openapi.yaml` 的 schema 返回**结构正确但内容是随机**的数据，足够把页面结构、状态流转、错误态全部写完。

**mock 的三个坑**（提前告诉你，省得你以为是前端 bug）：

1. mock **不校验 CSRF、不返回 cookie**，所以 401/403 的交互要在路径 A 才能验。
2. mock 的 `items` 可能返回空数组——把空态写好，真后端也可能返回空。
3. mock 不会帮你验证「响应里没有分数字段」这类约定，那要靠 `scripts/check-redlines.mjs` + 路径 A。

**mock 里建议手工补的数据**（真后端能用演示账号直接看到）：
`space/state` 的四种 state、`recommendations` 多候选且 `unknowns` 非空、`matches` 的 `pending`/`connected` 两种、消息历史 ≥20 条、401/403/429 三种错误态。

---

## 5. 路径 C：只想先看接口

1. 打开 `api/API-CONTRACT.md`，第 4 节是一张接口清单（标了哪些今天能用、哪些待迁移）。
2. `api/openapi.yaml` 可直接拖进 Apifox / Postman / Swagger Editor 看树形结构。
3. 注意区分两类接口：
   - `x-contract-status: implemented`（17 个操作）→ **现在就能调**
   - `x-contract-status: planned`（10 个操作）→ 能力已实现但**还没搬到 `/api/v1`，且当前无鉴权，请先不要依赖**，迁移完成后会通知你

---

## 6. 必须做：同源代理（否则一定连不上）

后端**没有配 CORS**，且 session cookie 是 `SameSite=Lax`，所以浏览器直连后端会被拦。做法：

1. 把 `web-lib/proxy-route.ts` 放到你的项目里，路径必须是
   `app/api/proxy/v1/[...path]/route.ts`
2. 设环境变量 `API_BASE_URL=http://127.0.0.1:8000`（见 `web-lib/api/client.ts` 里的默认值）
3. 前端所有请求走同源 `/api/proxy/v1/*`，**不要**写后端绝对地址

做完后自测一条：

```ts
const me = await fetch("/api/proxy/v1/auth/me", { credentials: "include" });
// 未登录应为 401（不是 CORS 报错，也不是 404）
```

> 如果你最终要和后端**分域部署**（不同域名），代理也解决不了 cookie 的作用域问题，需要后端加 `CORSMiddleware(allow_credentials=True)` + `cookie_samesite=none; secure`（要求 HTTPS）。这属于后端改动，请提前提。

---

## 7. 把类型接进你的项目（3 步）

1. 把 `web-lib/api/` 整个目录复制到你项目的 `lib/api/`（或任何位置，只要 import 路径对）。
2. 确认 `tsconfig.json` 有 `"strict": true`（这两个文件在 strict 下零错误，别为了省事关掉）。
3. 用法：

```ts
import { authApi, spaceApi, recommendationApi, openMatchSocket } from "@/lib/api/client";

const me = await authApi.me(() => router.push("/login"));       // 401 自动回调
const { state, can_match } = await spaceApi.state();            // 决定渲染哪个页面
const recos = await recommendationApi.generate();               // 推荐（无任何分数字段）
const ws = openMatchSocket(matchId, { onMessage: appendOnce }); // 已按 id 去重
```

`client.ts` 已经处理的三件容易写错的事：CSRF 双提交（自动读 cookie 并加 `X-CSRF-Token`）、统一错误（`ApiError` 带 `code`/`trace_id`/`details`）、WebSocket 重复消息去重。

> 如果你不用 `client.ts` 自己写 fetch，请务必保证：写操作带 `X-CSRF-Token`（值等于 cookie `tongpin_csrf`）、`fetch` 用 `credentials: "include"`。

---

## 8. 联调自检（写一阶段跑一次）

```bash
python -m scripts.smoke_e2e          # 17 项链路检查：CSRF / 状态机 / 证据可溯源 / 幂等 / WS / 401
node scripts/check-redlines.mjs src  # 扫你的前端源码里有没有红线词（把 src 换成你的源码目录）
```

`smoke_e2e` 检查的是后端；`check-redlines` 检查的是你的代码。两个都过，基本可以交付。

想完整对齐验收口径，看 `api/API-CONTRACT.md` 第 7 节：那里有「脚本之外还要人眼确认」的部分（比如：卡片的「还不确定」区块必须真的渲染出来，不能被折叠或隐藏）。

---

## 9. 常见问题排查表

| 症状 | 原因 | 处理 |
|---|---|---|
| `fetch` 报 CORS / 预检失败 | 直连了后端 | 改用同源代理（第 6 节），前端不要出现 `127.0.0.1:8000` 绝对地址 |
| 登录返回 200，但下一个请求 401 | cookie 没落地 | 检查代理有没有透传 `Set-Cookie`（要逐条 append，不能合并；`proxy-route.ts` 已处理）；检查 `credentials: "include"` |
| 写操作 403 `CSRF_INVALID` | 没带 `X-CSRF-Token` 或值不对 | **这是前端 bug，不要弹给用户**。用 `client.ts`，或确认读的是 `tongpin_csrf` 而不是 `tongpin_session` |
| 403 `CONSENT_REQUIRED` | 用户还没授权（`details.scope` 告诉你缺哪个） | 走"说明用途 → 用户点同意 → `POST /api/v1/consents`" |
| 429 | 触发限流（LLM 类接口 6 次/分钟） | 按 **HTTP 状态 429** 判断并退避重试（⚠️ 它的 `code` 是通用的 `HTTP_ERROR`，别按 code 判断） |
| WebSocket 立即关闭 `4401` | 握手 cookie 没带过去 | WS 不能走 Route Handler 代理，要直连或用 Nginx/Caddy 转发升级请求 |
| WebSocket 关闭 `4403` | 你不属于这个 match | 用 `GET /api/v1/matches` 里 `status === "connected"` 的 `match_id` |
| 消息重复渲染 | 历史回放 + 自己 POST 成功各来一次 | 按 `data.id` 去重（`openMatchSocket` 已内建） |
| `tsc` 报 `Cannot find name 'process'` | 项目缺 `@types/node` | 装 `@types/node`（`client.ts` 已用模块作用域声明兜底，正常不该出现） |
| `space/state` 的 `question.options` 是空数组 | 后端已知问题 | 用 `GET /api/v1/questionnaire` 取题库，按 `dimension` 匹配（见契约 5.5） |
| 时间字段格式不一致 | `/consents` 返回 `+00:00`，其它返回 `Z` | 一律用 `new Date()` 解析，**不要做字符串比较或截取**（见契约 1.5 例外说明） |

---

## 10. 红线（贴在你屏幕边上）

界面上**不允许**出现：

> 匹配度、契合度、相似度、百分比、分数、排名、星级、等级、人格报告、MBTI、性格类型、用户标签、用户画像

应该使用的表达：

> **Your Story**、**How I See You**、共同点、差异、罕见共同点、世界观差异

三条容易踩的：

1. 后端响应里**没有** `score` / `percent` / `rank` / `level` 字段——这是刻意的，不要自己算一个。
2. `entropy`（0 ~ 0.6931）表示"**我们有多不确定**"，不是"你们有多配"。可以拿来做"还在了解你"这类可视化，**不得**换算成百分比。
3. 推荐卡片的 `unknowns`（还不确定的部分）**必须渲染**——它是产品诚实感的来源，不能折叠、不能隐藏。

（`scripts/check-redlines.mjs` 能自动扫 1 和 2 的低级形式：字段名与红线词。）

---

## 11. 遇到问题怎么反馈（这样问最快）

```
接口：POST /api/v1/matches/{match_id}/messages
现象：返回 403，body 是 {"code":"MATCH_NOT_CONNECTED",...}
trace_id：（响应头 X-Trace-Id 或 body.trace_id）
复现：登录 demo1@example.com / 用 GET /matches 里 pending 的那条 match_id
期望：____
```

带上 `trace_id` 我可以直接定位到后端日志。**契约与实现对不上时优先怀疑契约**——直接告诉我，我会改契约并通知你。

---

## 12. 版本与更新

| 项 | 值 |
|---|---|
| 契约版本 | v1（`/api/v1`） |
| 基准 commit | `3ddff2a` |
| 问卷版本 | `relationship-signals-v0.1`（提交时必须回传 `GET /api/v1/questionnaire` 返回的 `version`） |
| 待迁移 | 10 个 Agent 能力接口（猜测卡/信念/匹配叙事等），迁移完成后通知 |
| 已知待修 | 见 `api/API-CONTRACT.md` 第 9 节（共 6 项，都给了绕过方式） |
