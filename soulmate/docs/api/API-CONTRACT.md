# SoulMate Agent · 前端对接契约（v1）

> 基准代码：`soulmate` @ commit `e2d2401`（v1 entropy bridge + recommendations evidence）
> 生成方式：由后端真实 `app.openapi()` 导出（31 条路径 / 40 个 schema）逐条核对后整理，**字段名均非臆造**
> 配套文件：`openapi.yaml`（OpenAPI 3.1，可导入 Postman / Apifox / 用 Prism 起 mock）、`../../web/lib/api/types.ts`、`../../web/lib/api/client.ts`

---

## 0. 一句话总览

前端只对接 **`/api/v1/*`** 一套接口，用 **同源代理** 转发，认证靠 **session cookie + CSRF 双提交**，业务上只有四个页面状态（EXPLORING → SELF_PROFILE_READY → MATCHING → CHAT），**永远不展示任何分数、百分比、排名、等级**。

---

## 1. 接入方式（先看这节，否则一定连不通）

### 1.1 Base URL

| 环境 | 后端地址 |
|---|---|
| 本地 | `http://127.0.0.1:8000` |
| 线上 | 待定（换掉 host 即可，路径不变） |

业务接口前缀统一为 **`/api/v1`**。健康检查在 `GET /health`（无前缀，不需要认证）。

### 1.2 ⚠️ 浏览器不能直连后端（重要）

后端**没有配置任何 CORS 中间件**，且 session cookie 的 `SameSite=Lax` 会阻止跨站 XHR 携带 cookie。所以：

- ❌ 前端页面里 `fetch("http://127.0.0.1:8000/api/v1/...")` → 预检失败 / cookie 不生效
- ✅ **方案 A（推荐）**：Next.js 同源代理，前端只请求自己的域
- ✅ 方案 B：后端加 CORS（需要后端改代码，见 1.6）

### 1.3 方案 A：同源代理（推荐）

前端所有请求打到同源 `/api/proxy/v1/...`，由 Route Handler 转发到后端。cookie 与 CSRF 全部留在前端同源域，无需 CORS。

`web/app/api/proxy/v1/[...path]/route.ts`：

```ts
import { NextRequest } from "next/server";

const BACKEND = process.env.API_BASE_URL ?? "http://127.0.0.1:8000";

export const dynamic = "force-dynamic";

async function forward(req: NextRequest, path: string[]) {
  const url = new URL(req.url);
  const target = `${BACKEND}/api/v1/${path.join("/")}${url.search}`;

  const headers = new Headers();
  // 只转发必要请求头；Cookie 与 CSRF 必须带上，Host/Origin 不要带
  for (const key of ["cookie", "content-type", "x-csrf-token", "accept"]) {
    const v = req.headers.get(key);
    if (v) headers.set(key, v);
  }

  const res = await fetch(target, {
    method: req.method,
    headers,
    body: ["GET", "HEAD"].includes(req.method) ? undefined : await req.arrayBuffer(),
    redirect: "manual",
  });

  const out = new Headers();
  for (const key of ["content-type", "x-trace-id"]) {
    const v = res.headers.get(key);
    if (v) out.set(key, v);
  }
  // Set-Cookie 必须逐条透传，且不能被压缩成一条
  for (const c of res.headers.getSetCookie?.() ?? []) {
    out.append("set-cookie", c);
  }

  return new Response(res.body, { status: res.status, headers: out });
}

export async function GET(req: NextRequest, { params }: { params: { path: string[] } }) {
  return forward(req, params.path);
}
export async function POST(req: NextRequest, { params }: { params: { path: string[] } }) {
  return forward(req, params.path);
}
```

> Next.js 14 的 `params` 是同步对象（14.x）；如果你用 Next 15 请改成 `await params`。
> WebSocket 不能走这个代理（Route Handler 不支持 WS 升级）。聊天实时通道二选一：直连 `ws://127.0.0.1:8000/api/v1/ws/matches/{id}`（本地开发可用），或生产环境由反向代理（Nginx/Caddy）负责升级转发。

### 1.4 认证与 CSRF 规则

登录/注册成功后，后端下发两个 cookie：

| Cookie | HttpOnly | 有效期 | 用途 |
|---|---|---|---|
| `tongpin_session` | 是 | 14 天 | 会话凭证，浏览器自动携带，JS 读不到 |
| `tongpin_csrf` | 否 | 14 天 | CSRF 令牌，**JS 必须读得到** |

规则（后端 `V1CSRFMiddleware` 的真实实现）：

- 仅当路径以 `/api/v1/` 开头、且方法是 `POST / PATCH / DELETE` 时才校验
- 必须同时满足：请求头 `X-CSRF-Token` 存在 **且** 等于 cookie `tongpin_csrf`
- 豁免路径：`POST /api/v1/auth/register`、`POST /api/v1/auth/login`
- 不满足 → `403 { code: "CSRF_INVALID" }`

前端读取（浏览器）：

```ts
export function readCsrfToken(): string | null {
  const m = document.cookie.match(/(?:^|;\s*)tongpin_csrf=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : null;
}
```

> 如果用同源代理，`document.cookie` 读到的是**前端域**的 `tongpin_csrf`（代理透传过来的），逻辑不变。

### 1.5 统一请求约定

- `Content-Type: application/json; charset=utf-8`
- 所有请求带 `credentials: "include"`（同源代理下可省略，但建议保留）
- 所有 id 均为 **字符串**（用户 id、match_id、claim id、evidence id 都是 string）
- 所有时间为 **UTC ISO8601**，形如 `2026-09-12T10:00:00Z`
- `GET` 不产生副作用；写操作除 `client_message_id`（消息幂等）外不做幂等保证

### 1.6 方案 B：后端加 CORS（如果不想写代理）

需要后端在 `app/main.py` 加：

```python
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,          # 必须
    allow_methods=["*"],
    allow_headers=["*"],
)
```

并且 cookie 必须放宽：`COOKIE_SAMESITE=none` + `COOKIE_SECURE=true`（**需要 HTTPS**，本地 http 下 Chrome 会拒收 `SameSite=None; Secure` cookie）。**本地开发强烈建议用方案 A。**

---

## 2. 统一错误契约

### 2.1 错误响应体（`/api/v1/*` 全局统一）

```json
{
  "code": "CONSENT_REQUIRED",
  "message": "需要先授权匹配用途",
  "trace_id": "3f1a9c2e4b7d4e0f9a1b2c3d4e5f6071",
  "details": { "scope": "matching:v1" }
}
```

- 同时响应头带 `X-Trace-Id`（与 body 的 `trace_id` 一致）；前端报错时把 `trace_id` 一起上报
- **旧根路径**（`/users/{id}/*` 等）不走这套，仍是 FastAPI 默认的 `{"detail": ...}` —— 这也是必须迁移到 `/api/v1` 的原因之一
- 成功响应**不带** envelope，直接是业务 JSON

### 2.2 code 速查表

| HTTP | code | 触发场景 | 前端建议动作 |
|---|---|---|---|
| 400 | `INVALID_CANDIDATE` | 邀请自己 / candidate_id 非法 | 提示 + 刷新列表 |
| 400 | `QUESTIONNAIRE_VERSION_MISMATCH` | 提交的 `version` 与后端不一致 | 重新拉取问卷再提交 |
| 400 | `QUESTIONNAIRE_INCOMPLETE` | 必答题未答（`details.missing` 是缺失维度数组） | 滚动定位到缺失题 |
| 400 | `UNKNOWN_QUESTION` | 提交了题库里没有的 dimension | 重新拉取问卷 |
| 400 | `INVALID_ANSWER` | 选项 value 不在该题 options 内 | 重新拉取问卷 |
| 401 | `UNAUTHORIZED` | 未登录 / session 过期或已登出 | 跳登录页，清空本地态 |
| 401 | `INVALID_CREDENTIALS` | 登录邮箱或密码错 | 表单内提示，不跳转 |
| 403 | `CSRF_INVALID` | 缺少或不匹配 `X-CSRF-Token` | **检查 client 是否漏带头部**，不要提示用户 |
| 403 | `CONSENT_REQUIRED` | 未授予所需 scope（`details.scope`） | 弹出授权说明并调 `POST /api/v1/consents` |
| 403 | `FORBIDDEN` / `MATCH_NOT_CONNECTED` | 不在该 match 内 / 尚未 connected 就发消息 | 回退到匹配列表 |
| 404 | `NOT_FOUND` | 资源不存在或不属于当前用户 | 空态 |
| 409 | `EMAIL_TAKEN` | 邮箱已注册 | 提示改登录 |
| 409 | `INVITATION_CONFLICT` | 并发邀请冲突 | 重试一次 |
| 409 | `IDEMPOTENCY_CONFLICT` | 同 `client_message_id` 撞库 | 用新 id 重发 |
| 422 | `VALIDATION_ERROR` | 参数校验失败（`details.errors` 是 FastAPI 原始错误数组） | 开发期排查用 |
| 429 | `HTTP_ERROR` + `message: "rate_limited"` | 触发限流 | 按状态码 429 处理：退避重试 + "慢一点"提示。⚠️ 目前 code 是通用的 `HTTP_ERROR`，不是 `RATE_LIMITED`，请**按 HTTP 状态判断** |
| 500 | `INTERNAL_ERROR` | 服务异常 | 兜底错误页 + 上报 trace_id |

### 2.3 限流规则（后端 `RateLimiter`，按用户维度）

| 级别 | 额度 | 覆盖接口 |
|---|---|---|
| LLM | 6 次 / 60 秒 | `profile/refresh`、`elicitations`、`match-insights`、`story` 等会真实扣费的接口 |
| WRITE | 30 次 / 60 秒 | 作答、提交问卷等写操作 |
| READ | 120 次 / 60 秒 | 读接口 |

> 目前限流只挂在旧根路径的 agent 接口上；迁移到 `/api/v1/me/*` 时要一并带过去。

---

## 3. 页面状态机（前端路由与渲染的唯一依据）

`GET /api/v1/space/state` 返回当前用户应当处于的界面，**前端不要自己推断状态**。

```json
{ "state": "SELF_PROFILE_READY", "question": null, "profile": null, "can_match": true }
```

| state | 含义 | 前端渲染 |
|---|---|---|
| `EXPLORING` | 尚未授予 `matching:v1`，或必答题未答完 | 引导页 + 问卷（题库取 `GET /api/v1/questionnaire`） |
| `SELF_PROFILE_READY` | 已授权且必答题完成，但还没生成过推荐 | "Your Story" 自述页 + 一个「看看可能的人」按钮（触发 `POST /api/v1/recommendations`） |
| `MATCHING` | 已经生成过推荐会话 | 推荐列表页（`POST /api/v1/recommendations` 可重新生成） |
| `CHAT` | 已存在 `connected` 的 match | 直接进聊天页（`GET /api/v1/matches` 找 `status === "connected"` 那条） |

字段说明：

| 字段 | 类型 | 说明 |
|---|---|---|
| `state` | `"EXPLORING" \| "SELF_PROFILE_READY" \| "MATCHING" \| "CHAT"` | 见上表 |
| `question` | `object \| null` | 下一道未答的题 |
| `question.id` / `question.dimension` / `question.prompt` | string | 题目标识与题干 |
| `question.options` | array | ⚠️ **后端目前恒返回 `[]`**（未实现）。取选项请用 `GET /api/v1/questionnaire` 的完整题库，按 `dimension` 匹配 |
| `profile` | `null` | 预留字段，目前恒为 `null`，前端不要依赖 |
| `can_match` | boolean | 是否满足"可开始匹配"的前置条件（已授权 + 必答完成） |

依据的后端判据顺序：存在 `connected` match → `CHAT`；否则 `can_match = 已授权 matching:v1 && 必答题全答`；`can_match` 且已存在推荐会话 → `MATCHING`；`can_match` 且未生成 → `SELF_PROFILE_READY`；否则 `EXPLORING`。

---

## 4. 接口清单

### 4.1 ✅ 今天就能调用（已实现于 `/api/v1`，共 14 个）

| 方法 | 路径 | 用途 | 认证 | 需授权 scope |
|---|---|---|---|---|
| POST | `/api/v1/auth/register` | 注册并自动登录 | — | — |
| POST | `/api/v1/auth/login` | 登录 | — | — |
| POST | `/api/v1/auth/logout` | 登出（撤销 session） | ✔ | — |
| GET | `/api/v1/auth/me` | 当前用户 | ✔ | — |
| GET | `/api/v1/questionnaire` | 取题库（含选项与极性） | — | — |
| POST | `/api/v1/questionnaire/submissions` | 提交问卷 → 生成 Claim | ✔ | `matching:v1` |
| GET | `/api/v1/claims` | 我的 Claim 列表（"How I See You" 素材） | ✔ | `matching:v1` |
| POST | `/api/v1/consents` | 授权某个用途 | ✔ | — |
| GET | `/api/v1/consents` | 已授权列表 | ✔ | — |
| POST | `/api/v1/recommendations` | 生成推荐（含理由与证据） | ✔ | `matching:v1` |
| GET | `/api/v1/recommendations/{candidate_id}` | 取某人的推荐理由 | ✔ | `matching:v1` |
| POST | `/api/v1/invitations` | 发出邀请（双向即成 match） | ✔ | `conversation:v1`（双方） |
| GET | `/api/v1/matches` | 我的匹配列表 | ✔ | — |
| GET | `/api/v1/matches/{match_id}/messages` | 拉取消息历史 | ✔ | `conversation:v1`（双方） |
| POST | `/api/v1/matches/{match_id}/messages` | 发消息（幂等） | ✔ | `conversation:v1`（双方） |
| GET | `/api/v1/space/state` | 副状态机（决定去哪个页面） | ✔ | — |
| WS | `/api/v1/ws/matches/{match_id}` | 聊天实时通道 | ✔（cookie） | — |

### 4.2 🚧 待迁移（能力已实现，但当前挂在旧根路径，无鉴权，前端暂时不要直接用）

| 现状路径（旧） | 目标路径（迁移后） | 能力 |
|---|---|---|
| `POST /users/{id}/elicit` | `POST /api/v1/me/elicitations` | 生成猜测卡（带极性 + 期望信息增益） |
| `POST /users/{id}/respond` | `POST /api/v1/me/elicitations/{elicitation_id}/responses` | 作答 → 贝叶斯更新 |
| `GET /users/{id}/belief` | `GET /api/v1/me/belief` | 当前信念（α/β/熵/置信区间） |
| `POST /users/{id}/story` | `POST /api/v1/me/story` | Your Story 自述 |
| `GET /users/{id}/profile` | `GET /api/v1/me/profile` | 行为画像摘要（内部用） |
| `POST /users/{id}/profile/refresh` | `POST /api/v1/me/profile/refresh` | 重算画像（扣费，6/min） |
| `POST /users/{id}/match` | `POST /api/v1/me/match-insights` | 匹配叙事（共同点/差异/罕见共同点/世界观） |
| `POST /relationships/{a}/{b}/signals` | `POST /api/v1/relationships/{candidate_id}/signals` | 关系级证据（聊天分析护城河） |
| `POST /events` · `GET /users/{id}/events` | `POST /api/v1/events` · `GET /api/v1/me/events` | 行为埋点 |
| `/extensions/*` | —（不进前端契约） | 技能/插件管理，仅运维用 |

> 前端如果现在就要验证"信息熵那个玩法"，可以**临时**直连旧路径（本地开发、同机、无鉴权），但必须包在 `web/lib/api/legacy-agent.ts` 一个文件里，并标注 `// TODO: 迁移到 /api/v1 后删除`。相关类型已在 `types.ts` 中给出。

---

## 5. 逐接口契约

### 5.1 `POST /api/v1/auth/register`

注册并直接建立会话（免 CSRF）。

请求：

```json
{
  "display_name": "林屿",
  "email": "linyu@example.com",
  "password": "password123",
  "birth_year": 1994,
  "region": "上海"
}
```

| 字段 | 类型 | 必填 | 约束 |
|---|---|---|---|
| `display_name` | string | ✔ | 1–64 |
| `email` | string | ✔ | 3–320，必须含 `@` 且域名部分含 `.` |
| `password` | string | ✔ | 8–128 |
| `birth_year` | int \| null | — | 1900–2100 |
| `region` | string | ✔ | 1–32 |

响应 `200`：

```json
{
  "user": {
    "id": "1", "display_name": "林屿", "email": "linyu@example.com",
    "birth_year": 1994, "region": "上海", "role": "user", "status": "active"
  },
  "csrf_token": "x8Kd…"
}
```

同时 `Set-Cookie: tongpin_session`（HttpOnly）+ `tongpin_csrf`。**`csrf_token` 字段与 cookie 值一致**，前端存内存即可（cookie 也会自动带）。

错误：`409 EMAIL_TAKEN`、`422 VALIDATION_ERROR`。

### 5.2 `POST /api/v1/auth/login`

请求 `{ "email": "...", "password": "..." }`，响应与 register 同构（`AuthOut`）。错误：`401 INVALID_CREDENTIALS`。

### 5.3 `POST /api/v1/auth/logout`

无请求体。**需要 CSRF 头**。响应 `{ "status": "ok" }`，并清除两个 cookie。

### 5.4 `GET /api/v1/auth/me`

响应 `200`：

```json
{ "id": "1", "display_name": "林屿", "email": "linyu@example.com",
  "birth_year": 1994, "region": "上海", "role": "user", "status": "active" }
```

未登录 → `401 UNAUTHORIZED`。**前端启动时的会话探测就靠它**（401 即未登录，不需要额外接口）。

### 5.5 `GET /api/v1/questionnaire`

无需认证。响应 `200`：

```json
{
  "version": "relationship-signals-v0.1",
  "estimated_minutes": 12,
  "questions": [
    {
      "id": "life_weekend",
      "section": "生活节奏",
      "dimension": "life_weekend",
      "prompt": "一个理想的周末，你更想怎么度过？",
      "help_text": "请选择当前更接近你的情况",
      "kind": "single",
      "required": true,
      "options": [
        { "value": "stay_home", "label": "留在家里慢慢恢复", "polarity": "confirm" },
        { "value": "go_out", "label": "出去走走见朋友", "polarity": "disconfirm" },
        { "value": "mixed", "label": "半天在家半天出去", "polarity": "uncertain" }
      ]
    }
  ]
}
```

| 字段 | 说明 |
|---|---|
| `questions[].kind` | 目前恒为 `"single"`（单选）。`multi` 尚未实现 |
| `questions[].required` | 未答完则 `space/state` 停在 `EXPLORING` |
| `options[].polarity` | `confirm` / `disconfirm` / `uncertain`。**这是信息熵引擎的输入极性** |
| `options[].label` | 展示文本；提交时用 `value`，不是 `label` |

> ⚠️ **前端禁止**根据 `polarity` 改变视觉权重、排序或做任何暗示性标注（例如把 `confirm` 标成"更匹配"）。极性只用于后端贝叶斯更新与"为什么这么问"的文案。
> ⚠️ 提交时**用 `value`**（如 `"stay_home"`）；后端会把它映射成 `label` 写进熵引擎的作答记录。

### 5.6 `POST /api/v1/questionnaire/submissions`

需 `matching:v1` 授权 + CSRF 头。

请求：

```json
{
  "version": "relationship-signals-v0.1",
  "answers": { "life_weekend": "stay_home", "comm_reply_frequency": "daily" }
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `version` | string | 必须与 `GET /api/v1/questionnaire` 返回的 `version` 完全一致，否则 `400 QUESTIONNAIRE_VERSION_MISMATCH` |
| `answers` | map<string, string> | `dimension` → 选项 `value`。必答题缺项 → `400 QUESTIONNAIRE_INCOMPLETE`（`details.missing` 列出缺失维度） |

响应 `200`：`ClaimOut[]`（每个 dimension 一条）

```json
[
  {
    "id": "q0Z8…", "dimension": "life_weekend", "value": "stay_home",
    "claim_type": "preference", "evidence_ids": ["eL3k…"],
    "observed_at": "2026-09-12T10:00:00Z", "expires_at": "2026-10-12T10:00:00Z",
    "sensitivity": "L1", "user_editable": true, "user_confirmed": true,
    "correction_state": null
  }
]
```

语义：一次提交同时产生 ① `Evidence`（原始作答，`kind="questionnaire"`）② 每个维度一条 `Claim` ③ 熵引擎的 `Elicitation` + `Response`（幂等：同维度重复提交复用同一条 elicitation，不会重复累加后验）。`Claim.expires_at` 默认 30 天后，过期需重新确认。

### 5.7 `GET /api/v1/claims`

需 `matching:v1` 授权。响应 `ClaimOut[]`（同上，按 `observed_at` 倒序）。这是 "How I See You" / "Your Story" 页的数据源。

### 5.8 `POST /api/v1/consents` · `GET /api/v1/consents`

请求：

```json
{ "scope": "matching:v1", "purpose": "用于关系匹配" }
```

响应 `200`：

```json
{ "scope": "matching:v1", "purpose": "用于关系匹配", "granted_at": "2026-09-12T10:00:00Z" }
```

| scope | 解锁 |
|---|---|
| `matching:v1` | 提交问卷、读 claims、生成/读取推荐 |
| `conversation:v1` | 发邀请、读写消息（**双方都需授权**） |

`GET` 返回已授权且未撤销的 `ConsentOut[]`。**前端必须在每次进入需要授权的动作前先查 `GET /api/v1/consents`**，不要靠本地缓存猜。

### 5.9 `POST /api/v1/recommendations`

需 `matching:v1` 授权 + CSRF 头。无请求体。响应 `200`：

```json
{
  "generated_at": "2026-09-12T10:00:00Z",
  "session_id": "rS9f…",
  "items": [
    {
      "recommendation_id": "rI2m…",
      "candidate_id": "2",
      "display_name": "林屿",
      "headline": "你们在「生活节奏」上比较接近，而「沟通频率」还不太确定",
      "common_signals": ["你们在「生活节奏」上的选择比较接近"],
      "differences": ["你们在「沟通频率」上的期待可能不同"],
      "unknowns": ["现在还不知道对方在「沟通频率」上的选择"],
      "how_to_continue": ["可以从一个具体生活场景开始聊"],
      "evidence_ids": ["eL3k…", "eM7p…"]
    }
  ]
}
```

前端渲染约定（**产品红线，逐条必须遵守**）：

| 字段 | 怎么用 | 禁止 |
|---|---|---|
| `headline` | 作为卡片主文案，直接展示 | 不要把它改写成"匹配度 87%"这类带数字的句子 |
| `common_signals` | 「共同点」区块 | — |
| `differences` | 「差异」区块（中性、好奇的语气，不是缺点） | 不要用"不合适/冲突/扣分" |
| `unknowns` | 「还不确定」区块 —— **这是产品的诚实感来源，不要藏起来** | 不要留空不渲染 |
| `how_to_continue` | 「可以这样开始」的建议句 | 不要改写成命令式 |
| `evidence_ids` | 「为什么这么想」展开时，用它调后端取依据；或直接忽略 | **不要把 id 字符串渲染给用户**；不要用数量做"证据强度"打分 |

排序即返回顺序，**前端不得重排、不得二次打分**。响应中**没有**任何 `score` / `percent` / `rank` / `level` 字段——这是刻意的，不是遗漏。

### 5.10 `GET /api/v1/recommendations/{candidate_id}`

`candidate_id` 是**数字**路径参数（≥1，这里与其它 id 是字符串不同，注意类型）。响应结构与 `POST` 同构，`items` 只含该候选人一条。未生成过 → `404 NOT_FOUND`。

### 5.11 `POST /api/v1/invitations`

需 `conversation:v1`（**双方**都要有）+ CSRF 头。

请求：

```json
{ "candidate_id": "2", "message": "想从一个具体场景开始了解。" }
```

⚠️ `candidate_id` 在这里是**字符串**（后端 `int()` 转换，非法值报 `400 INVALID_CANDIDATE`）；与 5.10 的路径参数类型不同。

响应 `200`：

```json
{ "match_id": "mT4q…", "status": "pending" }
```

`status` 语义：`pending` = 我已发出、对方未回应；对方回邀后自动变 `connected` 并写入 `connected_at`。**只有 `connected` 才能发消息**。不能邀请自己（`400`）。

### 5.12 `GET /api/v1/matches`

响应 `200`：

```json
[
  { "match_id": "mT4q…", "candidate_id": "2", "status": "connected", "connected_at": "2026-09-12T10:00:00Z" },
  { "match_id": "mT5r…", "candidate_id": "3", "status": "pending", "connected_at": null }
]
```

`status` ∈ `pending` / `connected`。`connected_at` 未连接时为 `null`。排序：`connected_at` 倒序优先，其次 `created_at` 倒序。

### 5.13 `GET /api/v1/matches/{match_id}/messages`

需 `conversation:v1`（双方）+ 认证。响应 `200`：

```json
[
  {
    "id": "mS8x…", "conversation_id": "mT4q…", "sender_id": "1",
    "body": "最近有什么小事让你觉得生活变好了？",
    "client_message_id": "uuid-1",
    "created_at": "2026-09-12T10:00:00Z", "read_at": null
  }
]
```

按 `created_at` 升序。注意 `conversation_id` 就是 `match_id`（同一值，字段名不同）。

### 5.14 `POST /api/v1/matches/{match_id}/messages`

请求：

```json
{ "body": "最近有什么小事让你觉得生活变好了？", "client_message_id": "uuid-1" }
```

| 字段 | 约束 |
|---|---|
| `body` | 1–4000 |
| `client_message_id` | 1–128，**前端生成 uuid**，用于幂等 |

响应 `200`：单条 `MessageOut`（结构同上）。

- **幂等**：同 `match_id` + 同 `sender_id` + 同 `client_message_id` → 直接返回已存在的那条（`200`），不会重复入库。前端重试安全。
- 并发撞库 → `409 IDEMPOTENCY_CONFLICT`（换新 id 重发）
- match 非 `connected` → `403 MATCH_NOT_CONNECTED`
- 不在该 match 内 → `403 FORBIDDEN`

### 5.15 `GET /api/v1/space/state`

见第 3 节。

### 5.16 `WS /api/v1/ws/matches/{match_id}`

认证：握手时读 cookie `tongpin_session`（**不能**用 `X-CSRF-Token`，浏览器 WS API 不支持自定义头）。失败即关闭：

| 关闭码 | 含义 |
|---|---|
| `4401` | 未登录 / session 失效 |
| `4403` | match 不存在或你不属于该 match |

连接成功后服务端立刻推送（注意：**目前是逐条推送，不是一次性快照**）：

```
{"type":"messages.snapshot","data":[]}          // 快照占位，data 恒为空数组
{"type":"message.created","data":{"id":"mS8x…","body":"…"}}   // 历史消息逐条回放
```

之后每当该 match 有新消息，服务端广播：

```
{"type":"message.created","data":{"id":"…","body":"…"}}
```

前端处理建议：

- 收到 `messages.snapshot` → 清空本地消息列表
- 收到 `message.created` → 按 `data.id` 去重后追加；如果是自己刚 POST 成功的消息（同 id），直接跳过（防止重复渲染）
- 心跳：服务端目前不要求也不发送心跳；前端可自行定时 `send("ping")`（服务端会忽略内容，仅用于保活）
- ⚠️ 事件体 `data` 只有 `id` 和 `body`，**没有** `sender_id` / `created_at`。需要完整字段就调 `GET /api/v1/matches/{match_id}/messages` 补全，或推动后端把事件体改全（建议提给后端）

---

## 6. 产品红线（前端硬约束，评审必查）

### 6.1 禁止出现的字段与文案

后端刻意不返回，前端也**不得自行计算或展示**：

- ❌ 匹配度 / 契合度 / 相似度，任何百分比、分数、进度条
- ❌ 排名、星级、等级、指数、评分
- ❌ 人格报告、MBTI、性格类型、用户标签、用户画像、标签云

替代用词（必须统一）：

| 不要用 | 用 |
|---|---|
| 匹配度 87% | 你们在「生活节奏」上比较接近 |
| 人格报告 / 画像 | **Your Story** / **How I See You** |
| 标签 | 具体的说法（直接引用 `Claim.value` 对应的选项 `label`） |
| 不合适 | 期待可能不同 |
| 匹配失败 | 现在还不确定 |

### 6.2 `belief_entropy` 这类量的正确用法

后端在 5.16 之前的 agent 接口里会给出 `entropy`（0 ~ 0.6931，伯努利熵）与 `belief_*`：

- ✅ 可以用于"我们还在了解你"这类**不确定性可视化**（例如"还很模糊 → 渐渐清晰"的文案/图形）
- ❌ **不得**换算成百分比、不得与"匹配好坏"挂钩、不得展示给用户"你现在 62% 明确"
- 产品语义：熵是**我们有多不确定**，不是**你们有多配**。这两个量在旧接口里就是分开的（`match_uncertainty` vs `belief_entropy`），前端不要把二者混为一谈

### 6.3 证据可解释性

每个推荐理由都带 `evidence_ids`，指向用户真实的作答记录。前端做"为什么这么想"的展开时：

- ✅ 展示依据的**文本**（例如"你在问卷里选了『留在家里慢慢恢复』"）
- ❌ 不要展示 id、不要展示条数作为"可信度"、不要让用户以为这是算法黑箱打分

### 6.4 授权与隐私

- 每次涉及匹配/聊天的动作前，先 `GET /api/v1/consents` 确认 scope；缺失时走"说明用途 → 用户点击同意 → `POST /api/v1/consents`"的显式流程
- 不要把 `Claim` 原始数据放进 URL query（会进日志与浏览器历史）
- 登出必须调 `POST /api/v1/auth/logout`（服务端撤销 session），不能只清前端状态

---

## 7. 联调 Checklist（按顺序跑一遍即可验收）

1. `POST /api/v1/auth/register` 建号 A → 断言收到两个 cookie、`auth/me` 返回自己
2. `GET /api/v1/space/state` → 断言 `EXPLORING`
3. `POST /api/v1/consents`（`matching:v1`）→ 断言 `GET /api/v1/consents` 能看到
4. `GET /api/v1/questionnaire` → `POST /api/v1/questionnaire/submissions`（带 `version` 与全部必答 dimension）→ 断言返回 `Claim[]` 且 `evidence_ids` 非空
5. `GET /api/v1/space/state` → 断言 `SELF_PROFILE_READY` 且 `can_match === true`
6. 建号 B，同样授权 + 答题
7. 用 A 调 `POST /api/v1/recommendations` → 断言 `items[].evidence_ids` 非空、响应里**没有**任何分数字段
8. A `POST /api/v1/invitations`（`candidate_id` = B 的 id）→ `status: "pending"`；此时 A 发消息应得 `403 MATCH_NOT_CONNECTED`
9. B 回邀 A → `status: "connected"`
10. A `POST /api/v1/matches/{match_id}/messages`（`client_message_id: "uuid-1"`）→ 再用同 id 重发 → 断言返回**同一条** `id`
11. 连 `WS /api/v1/ws/matches/{match_id}` → 断言先收 `messages.snapshot`，再收历史 `message.created`
12. 用无 cookie 的客户端调 `GET /api/v1/auth/me` → 断言 `401 UNAUTHORIZED`
13. 故意不带 `X-CSRF-Token` 调 `POST /api/v1/consents` → 断言 `403 CSRF_INVALID`
14. `POST /api/v1/auth/logout` → 再调 `auth/me` → 断言 `401`

### 本地起服务

```bash
cd F:\Codex\SoulMate\soulmate
python -m alembic upgrade head                    # 初始化/升级数据库
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
# 交互式文档：http://127.0.0.1:8000/docs
# OpenAPI JSON：http://127.0.0.1:8000/openapi.json
```

测试账号：通过 `POST /api/v1/auth/register` 自助创建（数据库里没有预置账号）。

---

## 8. 前端可以马上开工的 mock 方案

`openapi.yaml` 可直接喂给 mock 工具，不需要等后端：

```bash
npx @stoplight/prism-cli mock openapi.yaml --port 4010
# 或导入 Apifox / Postman：New → Import → 选 openapi.yaml
```

需要在 mock 里重点造的数据：`space/state` 的四种 state、`recommendations` 的多候选（含 `unknowns` 非空的场景）、`matches` 的 `pending` 与 `connected` 两种、消息历史 ≥20 条、以及 401/403/429 三种错误态。

---

## 9. 变更与版本

| 项 | 值 |
|---|---|
| 契约版本 | v1（`/api/v1`） |
| 基准 commit | `e2d2401` |
| 问卷版本 | `relationship-signals-v0.1`（由 `GET /api/v1/questionnaire` 返回，提交时必须回传） |
| 已知待修（前端可先绕过） | ① `space/state.question.options` 恒为空 → 用 `GET /api/v1/questionnaire`；② 429 的 `code` 是 `HTTP_ERROR` → 按 HTTP 状态判断；③ WS `message.created` 缺 `sender_id`/`created_at`；④ agent 能力仍在旧根路径（见 4.2） |
