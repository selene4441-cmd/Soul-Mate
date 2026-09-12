# 同频匹配后交流技术方案 v0.1

## 1. 文档目的

本文定义“同频”在现有匹配产品基础上实现匹配后交流的技术方案，覆盖领域边界、数据模型、状态机、事务、API、WebSocket、Outbox、前端、安全、测试、部署和迁移顺序。

本文承接：

- [匹配后交流产品方案 v0.1](./conversation-product-design-v0.1.md)
- [关系信号与匹配指标 v0.1](./matching-metrics-v0.1.md)
- [同频 Web 产品技术方案 v0.1](./web-technical-architecture-v0.1.md)

若文档冲突，以同意、隐私和安全要求更严格的一方为准。本文描述目标技术基线，不代表当前代码已经全部实现。

## 2. 范围与非目标

### 2.1 范围

- `ConnectionRequest` 双向连接状态机。
- `Match`、`Conversation`、`ConversationMember` 生命周期。
- 基于关系线索的 `ConversationCue`。
- 文字消息、幂等发送、游标补拉和 WebSocket 更新。
- 结束交流、拉黑、举报和授权撤回。
- 站内通知和低频摘要任务。
- 事件、指标、审计、测试、部署和数据迁移。

### 2.2 非目标

- 不拆分聊天、通知和安全微服务。
- 不引入 Kafka、Kubernetes、Elasticsearch 或独立聊天中间件。
- 不在 v0.1 引入端到端加密。
- 不在 v0.1 实现群聊、语音、视频、附件和复杂消息类型。
- 不让 LLM 自动代替用户发送消息或扮演交流对象。
- 不让消息正文默认进入匹配训练、广告画像或通用分析。
- 不依赖 Redis 保存唯一业务真相。

技术演进采用“模块化单体优先、按真实瓶颈替换组件”的原则。

## 3. 核心技术决策

| 领域 | 决策 | 原因 |
|---|---|---|
| Web | Next.js 15 + React 19 + TypeScript | 与现有用户端一致，支持响应式和服务端渲染 |
| 前端状态 | TanStack Query + 少量组件状态 | 适合服务端状态、缓存、重试和乐观更新 |
| API | FastAPI + Pydantic v2 + SQLAlchemy 2 | 与现有后端、匹配和数据处理生态一致 |
| 数据库 | PostgreSQL 16 + Alembic | 事务、约束、JSON 和可追溯迁移能力完整 |
| 向量能力 | PostgreSQL + pgvector | 保留现有匹配能力，暂不拆独立向量库 |
| 实时通信 | 原生 WebSocket + Redis Pub/Sub | 满足当前规模，减少协议和基础设施复杂度 |
| 异步任务 | Celery + Celery Beat | 处理过期、通知、摘要、Outbox 和补偿任务 |
| 缓存与限流 | Redis 7 | 速率限制、短期状态和跨实例事件分发 |
| 部署 | Docker + Nginx/Caddy + 托管 PostgreSQL | 首批用户无需 Kubernetes |
| 观测 | OpenTelemetry + Sentry + 结构化日志 | 支持 trace、告警和脱敏 |
| 测试 | pytest + Vitest + Playwright | 覆盖领域、契约、前端和双账号端到端流程 |

后端继续采用同步 SQLAlchemy 领域服务。FastAPI 普通路由保持同步数据库语义，WebSocket 只作为异步适配层，不为了实时通信重写整个领域层为异步。

## 4. 总体架构

```text
用户浏览器
  |
  | HTTPS / WSS
  v
Nginx / Caddy
  |-------------------------------|
  v                               v
Next.js Web                   FastAPI
                                  |
                  +---------------+----------------+
                  |                                |
              PostgreSQL                         Redis
       业务真相 / Outbox / 审计          Pub/Sub / 限流 / 缓存
                  |
             Celery Worker + Beat
        过期 / 通知 / 摘要 / Outbox 转发
```

架构规则：

1. PostgreSQL 是连接、会话、消息和权限状态的唯一业务真相。
2. WebSocket 和 Redis 只负责实时分发，不决定业务是否成功。
3. 消息先提交 PostgreSQL，再写 Outbox，随后异步推送到在线连接。
4. 断线用户通过 REST 游标补拉，不依赖 WebSocket 事件重放。
5. 所有跨模块写入通过领域服务完成，API 路由不直接拼接状态变更。
6. Outbox 中只保存实体 ID、事件类型和版本，不复制消息正文。
7. 管理员和普通用户使用同一权限边界之外的两套明确授权路径。

## 5. 代码模块边界

现有 `interaction.py` 在实现阶段拆分为以下模块，并在迁移期保留兼容外观：

```text
services/backend/app/modules/
  connections.py      ConnectionRequest 状态机、冷却和过期
  conversations.py    Match、Conversation、成员和关闭规则
  messages.py         消息幂等、游标、发送和授权校验
  cues.py             议题生成、选择、版本和反馈
  blocks.py           拉黑关系及全局阻断检查
  notifications.py    站内通知、摘要和去重
  safety.py           举报、审核和用户安全动作
  realtime.py         Redis 事件编排和 WebSocket Hub
  audit.py            幂等和审计基础能力
  matching.py         现有推荐与解释能力
```

职责约束：

- `connections.py` 不直接发送消息。
- `messages.py` 不自行判断连接是否合法，先调用 `conversations.py` 和 `blocks.py`。
- `safety.py` 可以在同一事务中调用 `blocks.py`，但不得把审核内容写入普通日志。
- `notifications.py` 只消费业务结果，不反向修改连接和消息状态。
- `realtime.py` 不承载授权规则，只负责可信事件分发。

前端对应拆分：

```text
apps/web/
  app/(product)/requests/          连接请求
  app/(product)/messages/          会话列表和会话页
  components/conversation/         议题卡、消息、安全菜单
  lib/conversation/                API、WebSocket、游标和缓存
```

## 6. 数据架构

### 6.1 数据建模原则

- 用户关系使用稳定的 `pair_key`，由双方 ID 排序后哈希生成。
- 连接请求、连接关系、会话和消息使用不同实体，不混用状态。
- 会话成员状态按用户分别保存，不根据消息发送方推断。
- 消息正文和审计事件分离，审计只保存 ID、动作和哈希引用。
- 所有时间使用带时区的 UTC 时间存储，展示层转换为本地时间。
- 含正文的表必须配置保留期限和删除流程。
- 现有 UUID 十六进制字符串继续作为 ID，不进行无收益的 ID 体系迁移。

### 6.2 connection_requests

```text
id
pair_key
requester_id
recipient_id
recommendation_id
recommendation_session_id
source_feature_ids
cue_type
topic_text
personal_message
status
policy_version
expires_at
responded_at
decline_reason_private
created_at
updated_at
```

`status`：

```text
pending
accepted
declined
cancelled
expired
```

索引与约束：

```text
INDEX (recipient_id, status, created_at)
INDEX (requester_id, status, created_at)
INDEX (pair_key, status)
UNIQUE (pair_key) WHERE status = 'pending'
CHECK requester_id != recipient_id
```

`pair_key` 由服务层使用 `min(user_a, user_b) + ":" + max(user_a, user_b)` 后哈希生成，避免依赖数据库函数，兼容 SQLite 开发环境。

### 6.3 matches

现有 `matches` 表增加：

```text
pair_key
accepted_at
closed_at
closed_by
close_reason
```

建议状态：

```text
active
closed
blocked
```

约束：

```text
UNIQUE (pair_key)
INDEX (user_a_id, status, updated_at)
INDEX (user_b_id, status, updated_at)
```

迁移时将现有 `connected` 映射为 `active`。旧 `invited` 状态只允许通过数据迁移或兼容层处理，新代码不得继续创建旧状态。

### 6.4 conversations

现有 `conversations` 表增加：

```text
status
context_snapshot
opened_at
closed_at
last_message_at
```

`status`：

```text
active
closed
blocked
```

`context_snapshot` 只保存用户可见的共同点、差异、未知项、解释和来源版本，不包含 `ranking_score`、`success_probability` 或原始解释因子。

索引：

```text
INDEX (status, last_message_at)
UNIQUE (match_id)
```

### 6.5 conversation_members

```text
conversation_id
user_id
last_read_at
notification_state
exited_at
blocked_at
created_at
updated_at
PRIMARY KEY (conversation_id, user_id)
```

规则：

- 每个会话固定创建两名成员。
- `last_read_at` 只用于内部未读计数，不作为对方可见的精确已读时间。
- `notification_state` 支持 `normal` 和 `muted`。
- 任一成员 `exited_at` 后，会话进入 `closed`，双方停止发送。
- 拉黑关系仍由 `blocks` 表作为最终安全真相。

### 6.6 conversation_cues

```text
id
conversation_id
connection_request_id
cue_type
text
source_feature_ids
source_versions
status
created_by
created_at
updated_at
```

`cue_type`：

```text
common
difference
unknown
boundary
custom
```

`status`：

```text
active
answered
ignored
archived
```

议题文本是用户选择或确认后的产品内容。若未来使用 LLM 改写，必须保存模型版本、输入引用和用户确认状态，且不得默认包含原始私密文本。

### 6.7 messages

现有 `messages` 表增加：

```text
kind
reply_to_id
deleted_at
moderation_status
```

建议 `kind`：

```text
text
cue_response
system_cue
system_state
```

约束：

```text
UNIQUE (conversation_id, client_message_id)
INDEX (conversation_id, created_at, id)
INDEX (sender_id, created_at)
```

消息正文使用普通 Text 存储并依赖数据库、备份和磁盘加密。v0.1 不做应用层端到端加密，因为平台需要支持安全审核、举报处理和风险识别。未来若改变该决策，必须同时重设审核和通知产品能力。

### 6.8 blocks

```text
id
blocker_id
blocked_id
pair_key
reason_private
created_at
revoked_at
```

约束与索引：

```text
INDEX (blocker_id, blocked_id, revoked_at)
INDEX (pair_key, revoked_at)
CHECK blocker_id != blocked_id
```

发送消息、创建请求和接受请求都必须检查双向拉黑关系。读取或解除他人拉黑记录不得向普通用户开放。

### 6.9 safety_events

现有表建议增加：

```text
conversation_id
message_id
details_hash
```

规则：

- `message_id` 只作为受控引用，不复制正文到 `details_reference`。
- 普通日志、指标标签和 Outbox payload 不得包含举报原文。
- 审核人员只能在授权管理流程中读取必要内容。
- 举报不能因为消息已被普通删除而失去可审计引用。

### 6.10 notifications

新增：

```text
id
user_id
kind
entity_type
entity_id
dedupe_key
state
scheduled_at
delivered_at
read_at
created_at
updated_at
```

建议 `kind`：

```text
connection_request
connection_accepted
message_summary
conversation_closed
outcome_reminder
```

规则：

- `dedupe_key` 防止重复催促。
- 普通消息进入摘要任务，不逐条强制推送。
- 撤回、结束、拉黑或过期后取消未发送通知。

### 6.11 outbox_events

现有表建议增加：

```text
event_key
available_at
locked_at
locked_by
last_error
```

保留：

```text
id
topic
payload
status
attempts
created_at
processed_at
```

`payload` 只包含实体 ID、动作、版本和必要元数据。消费者收到 ID 后重新查询 PostgreSQL，再构造对用户可见的 DTO。

### 6.12 迁移顺序

1. 增加 `pair_key` 和可空生命周期字段。
2. 回填现有 Match、Conversation、Message 数据。
3. 校验 `pair_key` 唯一性并处理历史重复数据。
4. 增加新表、索引和约束。
5. 切换代码到双写或兼容读取。
6. 停止写入旧状态。
7. 添加非空约束并删除废弃兼容逻辑。

当前开发数据可以直接重建；预发布和生产迁移必须使用可回滚 Alembic 迁移，并先在数据库副本验证。

## 7. 领域流程与事务

### 7.1 创建连接请求

事务步骤：

1. 验证当前用户和 `matching:v1`、`conversation:v1`。
2. 验证候选关系、推荐解释快照和议题来源。
3. 计算 `pair_key`，检查双向拉黑和拒绝冷却期。
4. 条件插入 `pending` 请求；冲突时返回已有待处理请求。
5. 写 Outbox 和 Audit。
6. 提交事务。

创建请求不得创建 Match 或 Conversation。

### 7.2 接受连接请求

接受使用条件更新防止并发重复处理：

```sql
UPDATE connection_requests
SET status = 'accepted', responded_at = now()
WHERE id = :request_id
  AND recipient_id = :current_user_id
  AND status = 'pending'
RETURNING *;
```

同一事务继续：

1. 再查双方授权、安全状态和双向拉黑。
2. 创建 `Match`。
3. 创建 `Conversation`。
4. 创建两条 `ConversationMember`。
5. 创建首个 `ConversationCue`。
6. 写 Outbox、Notification 和 Audit。
7. 提交。

若 `pair_key` 已存在有效 Match，则返回已有关系，不重复创建会话。

### 7.3 拒绝和撤回请求

- 只有接收方可以拒绝 `pending` 请求。
- 只有发起方可以撤回 `pending` 请求。
- 拒绝和撤回使用条件更新，重复请求返回当前状态而不是再次修改。
- 拒绝原因默认私有，不进入发起方 DTO。
- 拒绝后写入冷却信息，但不得写敏感理由到普通指标。

### 7.4 发送消息

每次发送必须按顺序检查：

1. 当前用户已认证且 CSRF 校验通过。
2. 会话存在且当前用户是成员。
3. 会话状态为 `active`。
4. 双方 `conversation:v1` 均有效。
5. 双向不存在有效拉黑。
6. 消息长度、格式和速率限制通过。
7. 当前 `client_message_id` 尚未写入。

通过后在单事务中：

- 插入 Message。
- 更新 `conversations.last_message_at`。
- 写只包含 ID 的 Outbox。
- 提交。
- 由 Outbox 消费者推送 `message.created`。

客户端重复发送同一 `client_message_id` 时返回原消息，不重复写入或推送。

### 7.5 结束交流

- 任一成员可以单方面关闭会话。
- 使用条件更新将 `active` 改为 `closed`。
- 设置 `closed_by`、`closed_at` 和成员退出状态。
- 新增消息立即被拒绝。
- 历史保留策略由配置和隐私文档决定。
- 写 Outbox、Notification 和 Audit。

### 7.6 拉黑

拉黑是一个安全事务，必须同时：

1. 创建有效 Block。
2. 取消双方所有待处理 ConnectionRequest。
3. 关闭双方所有进行中的 Conversation。
4. 取消未发送的通知。
5. 写安全审计和最小化 Outbox。

拉黑判断不依赖 Conversation 状态。即使通过历史链接或其他入口重新创建请求，服务端仍必须拒绝。

### 7.7 撤回 conversation:v1

- `has_active_consent` 在每次发送时实时检查双方。
- 撤回后立即阻止新消息。
- 异步任务将相关进行中会话标记为 `closed` 或 `consent_revoked` 关闭原因。
- 撤回不自动删除对方依法或依协议仍可保留的历史，但必须在隐私策略中明确。
- 撤回事件不能包含消息正文。

## 8. 后端实现

### 8.1 路由分层

```text
HTTP route
  -> schema validation
  -> authentication / CSRF
  -> domain service
  -> transaction / Outbox
  -> response DTO
```

路由不得：

- 直接修改 ORM 对象状态并提交。
- 返回内部 `ranking_score`。
- 把完整请求体或消息正文写入日志。
- 自行实现拉黑、同意或会话状态规则。

### 8.2 错误码

建议新增：

```text
CONNECTION_REQUEST_NOT_FOUND
CONNECTION_REQUEST_ALREADY_RESOLVED
CONNECTION_REQUEST_EXPIRED
CONNECTION_REQUEST_COOLDOWN
CONVERSATION_NOT_FOUND
CONVERSATION_CLOSED
CONVERSATION_BLOCKED
MESSAGE_DUPLICATE
MESSAGE_RATE_LIMITED
BLOCKED_RELATIONSHIP
CONSENT_REVOKED
IDEMPOTENCY_CONFLICT
```

错误响应继续包含稳定 `code`、面向用户的 `message`、`trace_id` 和最小必要 `details`。

### 8.3 幂等

- 创建连接请求、接受、拒绝、消息、关闭、拉黑和举报支持 `Idempotency-Key`。
- 消息额外使用 `client_message_id`，保证客户端重试不会重复。
- 条件更新和唯一约束作为并发场景的最终防线。
- 不依赖“先查询再写入”作为唯一幂等手段。

### 8.4 事务边界

- 状态变更和 Outbox 写入在同一数据库事务。
- Redis 操作不加入数据库事务。
- 外部通知失败不回滚业务真相，由 Outbox 重试。
- 事务内不调用第三方 LLM、审核 API 或邮件服务。

## 9. API 契约

### 9.1 连接请求

```text
POST /api/v1/connection-requests
GET  /api/v1/connection-requests?direction=incoming|outgoing&status=pending
GET  /api/v1/connection-requests/{id}
POST /api/v1/connection-requests/{id}/accept
POST /api/v1/connection-requests/{id}/decline
DELETE /api/v1/connection-requests/{id}
```

创建请求示例：

```json
{
  "candidate_id": "candidate_id",
  "recommendation_session_id": "session_id",
  "cue_type": "difference",
  "topic_text": "忙碌时怎样保持联系感",
  "personal_message": "我想从这个问题开始了解。"
}
```

响应不得包含内部排序、成功概率或未编译的解释因子。

### 9.2 会话

```text
GET  /api/v1/conversations
GET  /api/v1/conversations/{id}
GET  /api/v1/conversations/{id}/messages?limit=50&after=...
POST /api/v1/conversations/{id}/messages
POST /api/v1/conversations/{id}/close
POST /api/v1/conversations/{id}/read
```

消息分页使用 `(created_at, id)` 游标，不使用容易漂移的页码。默认每页 50 条，服务端上限 100 条。

发送消息示例：

```json
{
  "client_message_id": "uuid",
  "body": "我愿意从这个问题开始聊。",
  "kind": "text",
  "reply_to_id": null
}
```

### 9.3 拉黑和举报

```text
GET    /api/v1/blocks
POST   /api/v1/blocks
DELETE /api/v1/blocks/{user_id}
POST   /api/v1/safety/reports
```

举报消息时至少提交：

```json
{
  "subject_id": "user_id",
  "conversation_id": "conversation_id",
  "message_id": "message_id",
  "event_type": "boundary_violation",
  "severity": "high",
  "details": "用户主动填写的说明"
}
```

举报说明只保存在受控数据路径中，不进入普通日志、分析事件或 Outbox。

### 9.4 兼容接口

迁移期保留：

```text
POST /api/v1/invitations
GET  /api/v1/matches
GET  /api/v1/matches/{match_id}/messages
POST /api/v1/matches/{match_id}/messages
WS   /api/v1/ws/matches/{match_id}
```

兼容层只做参数转换和 DTO 映射，不保留种子用户自动连接语义。新客户端必须使用 `connection-requests` 和 `conversations`。

## 10. 实时通信与 Outbox

### 10.1 WebSocket 端点

目标端点：

```text
WS /api/v1/ws/me
WS /api/v1/ws/conversations/{conversation_id}
```

- `/ws/me` 推送连接请求、接受、关闭和安全状态。
- `/ws/conversations/{id}` 推送会话消息和议题更新。
- Cookie、Origin、会话有效期和成员权限在建立连接时校验。
- 不通过查询参数传递长期令牌。
- 连接建立后先发送状态快照，再发送事件。

### 10.2 事件格式

```json
{
  "type": "message.created",
  "event_id": "event_id",
  "occurred_at": "2026-09-12T12:00:00Z",
  "data": {}
}
```

事件类型：

```text
connection.requested
connection.accepted
connection.declined
conversation.opened
conversation.cue.created
message.created
conversation.closed
conversation.blocked
messages.read
```

WebSocket 不是历史消息接口。客户端断线重连后必须重新拉取会话状态和游标消息。

### 10.3 Outbox 处理

1. 领域事务写业务表和 `outbox_events`。
2. Celery Beat 或独立 worker 锁定一批 `pending` 或可重试事件。
3. 消费者读取关联实体并校验当前状态。
4. 将最小 DTO 发布到 Redis Pub/Sub。
5. 当前实例中的 WebSocket Hub 接收后推送给连接。
6. 成功后标记 `processed`；失败则增加 `attempts`、设置 `available_at` 和 `last_error`。

并发消费使用 `locked_by`、`locked_at` 和条件更新，避免多个 worker 重复处理。Outbox 完成不代表消息对用户已读，只代表事件已分发。

### 10.4 Redis 频道

```text
tongpin:user:{user_id}:events
tongpin:conversation:{conversation_id}:events
```

频道 payload 只保留实体 ID、事件类型和版本。跨实例 worker 根据 ID 查询 PostgreSQL 后再推送。Redis 不可用时，消息仍能写入和读取，实时更新延迟，客户端降级为轮询。

## 11. 前端实现

### 11.1 页面结构

- `requests`：显示收到的连接请求和已发出的待处理请求。
- `messages`：左侧会话列表，右侧会话详情；移动端采用独立页面栈。
- 候选人详情：选择议题、编辑个人说明并发送请求。
- 安全菜单：静音、结束交流、拉黑和举报。

### 11.2 状态与缓存

TanStack Query key：

```text
["connection-requests", direction, status]
["connection-request", requestId]
["conversations"]
["conversation", conversationId]
["messages", conversationId, cursor]
```

WebSocket 事件只负责失效查询或更新已加载缓存，不作为唯一状态来源。发送消息使用 `client_message_id` 做乐观更新，服务端确认后按 ID 去重。

### 11.3 断线和重试

- WebSocket 使用指数退避和随机抖动重连。
- 页面恢复可见时重新校验会话和拉取游标。
- 发送失败保留草稿和重试按钮。
- 不把轮询和 WebSocket 造成的同一消息显示两次。
- 关闭、拉黑或授权失效后立即停止重连该会话并清除敏感缓存。

### 11.4 UI 安全边界

产品界面不得展示：

- 匹配百分比、星级和内部排序位置。
- 在线状态、输入中状态和精确“已读时间”。
- 系统议题伪装成对方消息。
- 拉黑详情告知对方。
- 未经用户确认的自动消息。

前端测试应阻止“已读不回”“最匹配”“命中注定”等压力性或确定性文案进入会话产品。

## 12. 安全、隐私与合规

### 12.1 权限矩阵

| 动作 | 发起方 | 接收方 | 其他用户 | 管理员 |
|---|---|---|---|---|
| 查看请求 | 是 | 是 | 否 | 审计授权后 |
| 撤回请求 | 仅 pending | 否 | 否 | 安全处理时 |
| 接受或拒绝 | 否 | 仅 pending | 否 | 不代替用户 |
| 读取会话 | 成员 | 成员 | 否 | 安全工单授权后 |
| 发送消息 | 成员且 active | 成员且 active | 否 | 否 |
| 结束会话 | 成员 | 成员 | 否 | 安全封禁时 |
| 拉黑 | 是 | 是 | 否 | 紧急安全处置 |
| 查看举报 | 举报人 | 被举报人不可见 | 否 | 授权审核人员 |

### 12.2 服务端控制

- Cookie 使用 `HttpOnly`、`Secure` 和 `SameSite`。
- 所有修改请求校验 CSRF 和 Origin。
- 消息正文不使用 `dangerouslySetInnerHTML`。
- ORM 查询全部参数化，不拼接用户输入 SQL。
- 登录、请求、消息、举报和管理接口实施分级速率限制。
- 管理端使用独立 RBAC、审计日志和最小权限原则。
- 备份、数据库和对象存储使用静态加密，密钥由 KMS 管理。
- 日志记录 ID、状态码和 trace，不记录消息正文和举报详情。
- 删除账号或数据权利请求必须覆盖数据库、缓存、通知和备份策略。

### 12.3 内容审核

v0.1 采用“举报驱动 + 规则护栏 + 管理端审核”：

- 先支持用户举报、拉黑和结束交流。
- 对高频邀请、群发相似内容、短时间大量消息和重复举报做规则检测。
- 需要第三方审核服务时，先做数据最小化和供应商安全评审。
- 不默认将全部私密会话上传给第三方模型。
- 审核结果以安全事件为准，不能仅凭模型分数自动永久封禁。

### 12.4 LLM 使用边界

- v0.1 的议题优先使用结构化模板，不依赖 LLM。
- 后续 LLM 只用于改写用户已选择的议题或提供候选表达。
- 发送前必须由用户确认。
- LLM 不接收不必要的消息正文。
- 不生成看似由对方发送的内容。
- 保存模型版本、模板版本和用户确认记录。

## 13. 可观测性与指标

### 13.1 日志和 Trace

每个 API 请求和任务包含 `trace_id`；Outbox 事件包含 `event_id` 和 `job_id`。日志允许记录：

```text
request_id
trace_id
user_id 的受控引用
connection_request_id
conversation_id
message_id
status
duration_ms
error_code
```

日志禁止记录消息正文、举报正文、Cookie、CSRF Token、密码和完整个人说明。

### 13.2 指标

- 连接请求创建数、接受率、拒绝率和过期率。
- 接受后会话开启率。
- 首轮回复率。
- 7 天对话存活率。
- 14 天满意度和 30 天边界尊重。
- 拉黑率、举报率和安全事件处理时间。
- WebSocket 连接数、重连率、事件延迟和 Outbox 积压。
- 消息发送失败率、幂等冲突率和游标补拉延迟。

标签中不得包含用户 ID、消息 ID 或自由文本，避免高基数和隐私泄露。

### 13.3 告警

- Outbox 积压或失败次数持续升高。
- WebSocket 推送延迟超出 SLO。
- 拉黑后仍发送消息的事件数大于 0。
- 撤回 consent 后仍发送消息的事件数大于 0。
- 举报处理时间超过策略阈值。
- 数据库、Redis 或 worker 不可用。

## 14. 测试策略

### 14.1 后端单元测试

- ConnectionRequest 每个状态转换。
- 条件更新和并发重复接受。
- 请求过期、撤回和拒绝冷却。
- Match、Conversation 和成员创建。
- 消息发送前的全部授权检查。
- 拉黑后的请求、接受和发送全部失败。
- 双方 consent 撤回后的发送失败。
- Outbox 重试和幂等。
- 游标排序和重复消息去重。

### 14.2 后端集成测试

使用两个真实测试账号完成：

```text
A 创建请求
B 查看请求
B 接受
双方获取会话
双方发送消息
一方关闭或拉黑
双方再次发送均失败
```

同时覆盖：

- 接受前消息发送返回 404 或 409。
- 重复 `Idempotency-Key` 不创建重复实体。
- 重复 `client_message_id` 不创建重复消息。
- 任一方撤回 `conversation:v1` 后停止发送。
- 举报关联消息但不改变对方可见 DTO。
- WebSocket 断开后 REST 游标可以补齐。

### 14.3 前端测试

- 请求接受、拒绝和过期状态。
- 议题选择、编辑和确认。
- 消息发送、失败重试和去重。
- 关闭、拉黑和举报流程。
- 禁止展示在线状态、精确已读压力和内部排序。
- 响应式页面和键盘可访问性。

### 14.4 契约和迁移测试

- OpenAPI 包含新增路径和错误码。
- 生成的 TypeScript 客户端与 OpenAPI 无差异。
- Alembic 可以从空数据库升级到最新。
- Alembic 可以从上一个正式版本升级并回填历史数据。
- 旧 `/invitations` 兼容层不产生自动连接。

### 14.5 验证命令

```powershell
.\.python312\python.exe -m pytest -q
.\.python312\python.exe -m ruff check .
pnpm --filter tongpin-web typecheck
pnpm --filter tongpin-web test
pnpm --filter tongpin-web build
pnpm --filter tongpin-web contracts
git diff --exit-code packages/contracts/client.ts
```

## 15. 部署与环境

### 15.1 本地环境

继续使用 Docker Compose：

```text
web
backend
worker
postgres + pgvector
redis
```

本地数据库可以使用 SQLite 运行文档和领域测试，但涉及事务、约束、并发和 Alembic 的验收必须使用 PostgreSQL。

### 15.2 预发布和生产

```text
Nginx / Caddy
  -> Next.js
  -> FastAPI 实例 A/B
  -> Celery Worker
  -> Celery Beat
  -> 托管 PostgreSQL
  -> 托管 Redis
```

- Alembic 作为独立发布步骤执行，不由每个 API 实例并发迁移。
- API 和 WebSocket 使用健康检查和优雅停机。
- Redis Pub/Sub 让多个 API 实例都能接收事件。
- 需要粘性会话时可以启用，但业务正确性不能依赖粘性会话。
- 定期恢复演练必须验证数据库备份和消息删除流程。

### 15.3 触发式演进

只有出现真实瓶颈时才替换组件：

- WebSocket 运维复杂度和并发连接明显增长时评估 Centrifugo。
- 事件量达到普通 PostgreSQL 查询无法承受时评估 ClickHouse。
- 多服务间需要可靠事件流时评估 NATS JetStream 或 Kafka。
- 搜索能力成为独立产品需求时评估 OpenSearch。

不得因为“以后可能使用”提前引入上述组件。

## 16. 实施计划

### 阶段一：契约与数据库

- 新增本文和产品文档回归测试。
- 新增 Alembic 迁移与回填脚本。
- 建立 `pair_key`、ConnectionRequest、Block 和 Notification 基础表。
- 保留现有接口兼容层。

退出条件：迁移可从当前版本和空库执行，数据库约束测试通过。

### 阶段二：双向连接

- 拆分连接、会话和消息领域模块。
- 实现请求创建、接受、拒绝、撤回和过期。
- 接受后创建 Match、Conversation、成员和首个议题。
- 移除真实流程中的种子自动连接。

退出条件：两个真实账号可以完成连接流程，所有权限测试通过。

### 阶段三：可靠消息

- 实现消息幂等、游标、双方 consent 检查和拉黑检查。
- 完成 Outbox 重试、Redis Pub/Sub 和 WebSocket Hub。
- 完成断线补拉和轮询降级。

退出条件：双实例环境下消息不重复、不丢失，断线后可补齐。

### 阶段四：安全与通知

- 完成结束、拉黑、举报、审核引用和通知去重。
- 完成 consent 撤回后的自动关闭。
- 添加速率限制、告警和隐私审计。

退出条件：安全动作秒级生效，举报和删除流程可追溯。

### 阶段五：体验与指标

- 接入议题卡、会话上下文和 7/14/30 天结果反馈。
- 完成事件指标看板和实验版本记录。
- 使用真实用户访谈校准邀请期限和通知频率。

退出条件：可以计算接受率、首轮回复率、7 天存活率和安全护栏指标。

## 17. v0.1 技术验收标准

1. PostgreSQL 是连接、会话和消息状态的唯一业务真相。
2. 接受前不存在可用 Conversation，无法通过任何接口绕过。
3. ConnectionRequest 的每个状态都有条件更新和测试。
4. 创建请求、接受、拒绝、关闭和拉黑支持幂等。
5. 双方 `conversation:v1` 在每次发送时实时校验。
6. 双向拉黑立即阻止请求、接受和消息发送。
7. 消息使用 `(conversation_id, client_message_id)` 去重。
8. 消息提交 PostgreSQL 后才产生成功响应和 Outbox。
9. Redis 或 WebSocket 不可用时，REST 仍能完成读写和补拉。
10. Outbox payload 不包含消息正文、举报详情或敏感解释因子。
11. WebSocket 采用 HttpOnly Cookie 鉴权，不通过长期查询参数传递令牌。
12. 多实例环境通过 Redis Pub/Sub 分发，且业务正确性不依赖内存 Hub。
13. 举报可以关联具体消息，但普通日志不保存正文。
14. OpenAPI、TypeScript 契约和数据库迁移测试全部通过。
15. 两个真实账号的端到端流程全部通过。

## 18. 待评审事项

- ConnectionRequest 默认有效期和拒绝冷却期是否保持 7 天、30 天。
- 结束交流后的历史保留方式。
- 是否允许用户自行解除拉黑。
- 是否引入应用层字段加密以及密钥轮换方案。
- 第三方内容审核服务是否符合数据驻留和隐私要求。
- 未来若要 Messages 参与匹配训练，所需的单独授权和数据最小化方案。
- 多实例 WebSocket 达到何种规模后切换 Centrifugo。
