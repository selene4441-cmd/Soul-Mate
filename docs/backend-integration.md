# 接入已有后端框架

同频的正式接口统一位于 `/api/v1`，FastAPI OpenAPI 是接口契约来源。已有后端最适合扮演三种角色之一。

## 方案 A：反向代理或 API 网关（推荐）

同伴的后端不复制 Claim、匹配或安全规则，只把请求透明转发到同频 FastAPI：

```text
浏览器
  |
  | HTTPS，同源 /api/v1
  v
同伴后端 / Nginx / Spring Cloud Gateway
  |
  | 内网 HTTP + Cookie + CSRF + WebSocket Upgrade
  v
同频 FastAPI
```

这种模式下，浏览器访问同伴域名的 `/api/v1`，因此：

- 不需要跨域 Cookie。
- HttpOnly 会话 Cookie 可以正常保存。
- CSRF Cookie 与 `X-CSRF-Token` 保持同源可读。
- WebSocket 可以复用同一域名。
- 同频仍负责身份、同意、匹配、安全和审计。

同伴后端必须保留以下信息，不能只转发 JSON：

| 项目 | 要求 |
|---|---|
| Header | 保留 `Cookie`、`X-CSRF-Token`、`Idempotency-Key`、`X-Session-Id`、`X-Trace-ID` |
| Response header | 保留 `Set-Cookie`、`X-Trace-ID` |
| WebSocket | 转发 `Upgrade: websocket` 和 `Connection: Upgrade` |
| 请求体 | 除必要鉴权外不要改写 API 请求体 |
| 数据库 | 不要直接连接同频 PostgreSQL；只调用 API |

### Nginx

可直接参考 [infra/nginx/tongpin.conf](../../infra/nginx/tongpin.conf)。

### Node.js / Express

安装 `http-proxy-middleware` 后：

```ts
import { createProxyMiddleware } from "http-proxy-middleware";

app.use(
  "/api/v1",
  createProxyMiddleware({
    target: process.env.TONGPIN_ORIGIN,
    changeOrigin: false,
    xfwd: true,
    ws: true,
    onProxyRes(proxyResponse) {
      delete proxyResponse.headers["content-length"];
    },
  }),
);
```

不要把 `changeOrigin` 设为 `true` 后仍期望同频根据原始 Origin 做安全判断。生产环境应同时设置同频的 `APP_ORIGIN` 为最终用户访问的域名。

### Spring Cloud Gateway

```yaml
spring:
  cloud:
    gateway:
      routes:
        - id: tongpin-api
          uri: ${TONGPIN_ORIGIN}
          predicates:
            - Path=/api/v1/**
        - id: tongpin-websocket
          uri: ${TONGPIN_ORIGIN}
          predicates:
            - Path=/api/v1/ws/**
```

网关不要自动改写 Cookie Path。若用户端和 API 最终使用不同域名，优先改成同站点子域名并统一 Cookie 策略，例如 `app.example.com` 与 `api.example.com`。

## 方案 B：已有后端作为前端 BFF

同伴后端可以先完成自己的登录，再把同频接口包装为自己的 BFF 接口。每个最终用户仍必须有独立的同频会话或映射关系，不能把所有用户共用一个会话。

后端调用顺序：

1. 用户明确授权后，调用 `/api/v1/auth/register` 或 `/api/v1/auth/login`。
2. 安全保存返回的 `tongpin_session` 和 `tongpin_csrf` Cookie。
3. 修改请求携带 `X-CSRF-Token`。
4. 问卷、邀请、结果等重复提交携带 `Idempotency-Key`。
5. 撤回授权调用 `DELETE /api/v1/consents/{scope}`。
6. 用户要求删除时调用 `DELETE /api/v1/privacy/me`。

服务端不要记录响应中的 Cookie、完整问卷答案、消息正文或删除后的审计正文。错误统一读取：

```json
{
  "code": "CONSENT_REQUIRED",
  "message": "需要先授权相应数据处理范围",
  "trace_id": "用于联系服务端排查",
  "details": {"scope": "matching:v1"}
}
```

## 方案 C：业务后端与自有用户体系直接集成

当前 v0.1 的用户接口采用浏览器会话和 CSRF 保护，尚未提供供第三方后端长期使用的服务账号、API Key 或 OAuth Client Credentials。因此，只拿一个后端框架还不能可靠地“服务端到服务端”直接调用。

如果同伴需要这种模式，需要新增一份独立契约，至少包括：

- 服务账号与密钥哈希，支持轮换和撤销。
- `matching:read`、`conversation:write`、`outcomes:write` 等明确作用域。
- 外部用户 ID 到同频用户 ID 的映射和删除同步。
- 请求签名、时间窗、防重放、幂等键和速率限制。
- 独立审计，不把密钥或原始内容写入日志。
- 安全事件优先级高于普通服务调用。

在这些能力实现前，推荐使用方案 A，或由同伴后端通过方案 B 管理每个用户的独立会话。

## 核心接口

| 接口 | 用途 |
|---|---|
| `POST /api/v1/auth/register` | 注册并建立会话 |
| `POST /api/v1/auth/login` | 登录并建立会话 |
| `GET /api/v1/consents` | 查看授权范围 |
| `POST /api/v1/consents` | 授权 |
| `DELETE /api/v1/consents/{scope}` | 撤回授权 |
| `GET /api/v1/questionnaire` | 获取问卷 |
| `POST /api/v1/questionnaire/submissions` | 提交问卷并生成 Claim |
| `POST /api/v1/recommendations` | 生成关系线索 |
| `POST /api/v1/invitations` | 发起连接 |
| `GET /api/v1/matches/{id}/messages` | 拉取消息 |
| `POST /api/v1/matches/{id}/messages` | 发送消息 |
| `WS /api/v1/ws/matches/{id}` | 实时消息 |
| `POST /api/v1/outcomes` | 提交 7/14/30 天结果 |

完整契约见 `packages/contracts/openapi.json`。更新接口后执行：

```bash
pnpm --filter tongpin-web contracts
git diff --exit-code packages/contracts/client.ts
```