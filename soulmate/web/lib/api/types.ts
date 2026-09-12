/**
 * SoulMate Agent API —— TypeScript 类型定义
 *
 * 基准：`soulmate` @ commit `e2d2401`
 * 配套：`docs/api/API-CONTRACT.md`（人读）、`docs/api/openapi.yaml`（机器可读）
 *
 * 约定（与 openapi.yaml 完全一致，改动请两边同步）：
 * - 所有 id 都是 string（唯一例外：`GET /api/v1/recommendations/{candidate_id}` 是 number）
 * - 所有时间是 UTC ISO8601 字符串，形如 `2026-09-12T10:00:00Z`
 * - 成功响应直接是业务 JSON；失败统一 `ErrorEnvelope`
 *
 * ⚠️ 产品红线（类型层面已体现，UI 层面必须自查）
 * - 响应里**没有** score / percent / rank / level 字段，前端不得自行计算或展示匹配度、百分比、星级、等级
 * - 禁止词：匹配度、契合度、相似度、人格报告、MBTI、用户标签、用户画像、分数、排名、等级
 * - `entropy` 只表示"我们有多不确定"，不得换算成百分比或与"匹配好坏"挂钩
 */

/* ------------------------------------------------------------------ 通用 */

/** UTC ISO8601，形如 `2026-09-12T10:00:00Z` */
export type IsoDateTime = string;

/** 字符串形式的 id */
export type Id = string;

/** `/api/v1/*` 全局统一错误码。429 目前是通用的 `HTTP_ERROR`，请按 HTTP 状态判断 */
export type ApiErrorCode =
  | "UNAUTHORIZED"
  | "INVALID_CREDENTIALS"
  | "CSRF_INVALID"
  | "CONSENT_REQUIRED"
  | "UNSUPPORTED_SCOPE"
  | "FORBIDDEN"
  | "MATCH_NOT_CONNECTED"
  | "NOT_FOUND"
  | "EMAIL_TAKEN"
  | "INVALID_CANDIDATE"
  | "INVITATION_CONFLICT"
  | "IDEMPOTENCY_CONFLICT"
  | "QUESTIONNAIRE_VERSION_MISMATCH"
  | "QUESTIONNAIRE_INCOMPLETE"
  | "UNKNOWN_QUESTION"
  | "INVALID_ANSWER"
  | "VALIDATION_ERROR"
  | "HTTP_ERROR"
  | "INTERNAL_ERROR";

/** 统一错误体；响应头同时带 `X-Trace-Id` */
export interface ErrorEnvelope {
  code: ApiErrorCode | string;
  message: string;
  trace_id: string;
  details: Record<string, unknown>;
}

/* -------------------------------------------------------------------- 认证 */

export interface UserOut {
  id: Id;
  display_name: string;
  email: string;
  birth_year: number | null;
  region: string;
  role: string;
  status: string;
}

export interface AuthOut {
  user: UserOut;
  /** 与 cookie `tongpin_csrf` 同值；存内存即可，cookie 会自动携带 */
  csrf_token: string;
}

export interface RegisterIn {
  /** 1–64 */
  display_name: string;
  /** 3–320，必须含 `@` 且域名部分含 `.` */
  email: string;
  /** 8–128 */
  password: string;
  /** 1900–2100 */
  birth_year?: number | null;
  /** 1–32 */
  region: string;
}

export interface LoginIn {
  email: string;
  password: string;
}

/* -------------------------------------------------------------------- 授权 */

/**
 * `matching:v1` 解锁问卷/claims/推荐；`conversation:v1` 解锁邀请与消息（双方都要有）；
 * `outcomes:v1` 后端已支持但当前无接口依赖，前端不要主动申请。
 * 传其它值 → 400 UNSUPPORTED_SCOPE。
 */
export type ConsentScope = "matching:v1" | "conversation:v1" | "outcomes:v1";

export interface ConsentIn {
  scope: ConsentScope;
  purpose: string;
}

export interface ConsentOut {
  scope: ConsentScope | string;
  purpose: string;
  /**
   * ⚠️ 与其它接口不一致：目前是 `2026-09-12T10:42:10.394960+00:00`
   * （带微秒、`+00:00` 后缀、没有 `Z`）。`new Date()` 能解析，但不要做字符串比较或截取。
   */
  granted_at: IsoDateTime;
}

/* -------------------------------------------------------------------- 问卷 */

/** 信息熵引擎的输入极性。⚠️ 前端禁止据此改变视觉权重、排序或做暗示性标注 */
export type OptionPolarity = "confirm" | "disconfirm" | "uncertain";

export interface QuestionnaireOption {
  /** 提交时用这个字段（不是 label） */
  value: string;
  label: string;
  polarity: OptionPolarity;
}

export interface QuestionnaireQuestion {
  id: string;
  section: string;
  /** 提交 `answers` 时的 key */
  dimension: string;
  prompt: string;
  help_text: string;
  /** 目前恒为 single */
  kind: "single" | "multi";
  /** 必答题未答完时，space/state 会停在 EXPLORING */
  required: boolean;
  options: QuestionnaireOption[];
}

export interface QuestionnaireOut {
  version: string;
  estimated_minutes: number;
  questions: QuestionnaireQuestion[];
}

export interface QuestionnaireSubmissionIn {
  /** 必须与 `GET /api/v1/questionnaire` 返回的 version 完全一致 */
  version: string;
  /** dimension → 选项 value。必答 dimension 缺失 → 400 QUESTIONNAIRE_INCOMPLETE */
  answers: Record<string, string>;
}

/* ------------------------------------------------------------------ claims */

export interface ClaimOut {
  id: Id;
  dimension: string;
  value: string;
  claim_type: string;
  /** 这条判断的依据（Evidence id）。展开"为什么这么想"时用；不要渲染 id 本身 */
  evidence_ids: Id[];
  observed_at: IsoDateTime;
  /** 默认 30 天后，过期需重新确认 */
  expires_at: IsoDateTime;
  sensitivity: string;
  user_editable: boolean;
  user_confirmed: boolean;
  correction_state: Record<string, unknown> | null;
}

/* ------------------------------------------------------------- 界面状态机 */

export type SpaceState = "EXPLORING" | "SELF_PROFILE_READY" | "MATCHING" | "CHAT";

export interface SpaceQuestion {
  id: string;
  dimension: string;
  prompt: string;
  /** ⚠️ 后端目前恒返回空数组，取选项请用 GET /api/v1/questionnaire */
  options: unknown[];
}

export interface SpaceStateOut {
  /** 前端路由的唯一依据，不要自己推断 */
  state: SpaceState;
  question: SpaceQuestion | null;
  /** 预留字段，目前恒为 null */
  profile: null;
  /** 已授权 matching:v1 且必答题全答 */
  can_match: boolean;
}

/** 状态 → 该渲染什么（照着写就行） */
export const SPACE_STATE_UI: Record<SpaceState, string> = {
  EXPLORING: "引导页 + 问卷（题库取 GET /api/v1/questionnaire）",
  SELF_PROFILE_READY: "Your Story 自述页 + 「看看可能的人」按钮",
  MATCHING: "推荐列表页",
  CHAT: "聊天页（从 GET /api/v1/matches 找 status === 'connected' 那条）",
};

/* -------------------------------------------------------------------- 推荐 */

/**
 * ⚠️ 刻意没有 score / percent / rank / level 字段 —— 不是遗漏。
 * 前端不得重排、不得二次打分、不得自行计算匹配度。
 */
export interface RecommendationItemOut {
  recommendation_id: Id;
  candidate_id: Id;
  display_name: string;
  /** 卡片主文案，由证据组合生成 */
  headline: string;
  /** 「共同点」 */
  common_signals: string[];
  /** 「差异」——中性好奇语气，不要写成"不合适/冲突" */
  differences: string[];
  /** 「还不确定」——**必须渲染**，这是产品诚实感的来源 */
  unknowns: string[];
  /** 「可以这样开始」建议句 */
  how_to_continue: string[];
  /** 理由依据。不要渲染 id、不要拿条数当"可信度" */
  evidence_ids: Id[];
}

export interface RecommendationsOut {
  generated_at: IsoDateTime;
  session_id: Id;
  /** 返回顺序即排序 */
  items: RecommendationItemOut[];
}

/* -------------------------------------------------------------------- 邀请 */

export interface InvitationIn {
  /** 字符串形式（后端转 int；非法值 → 400 INVALID_CANDIDATE）。不能邀请自己 */
  candidate_id: Id;
  message: string;
}

export type MatchStatus = "pending" | "connected";

export interface InvitationOut {
  match_id: Id;
  /** 双向邀请后自动变 connected；只有 connected 才能发消息 */
  status: MatchStatus;
}

/* -------------------------------------------------------------------- 匹配 */

export interface MatchOut {
  match_id: Id;
  /** 对方用户 id */
  candidate_id: Id;
  status: MatchStatus;
  connected_at: IsoDateTime | null;
}

export interface MessageIn {
  /** 1–4000 */
  body: string;
  /** 1–128，前端生成的 uuid；同值重发返回同一条消息（幂等） */
  client_message_id: string;
}

export interface MessageOut {
  id: Id;
  /** 与 match_id 同值 */
  conversation_id: Id;
  sender_id: Id;
  body: string;
  client_message_id: string;
  created_at: IsoDateTime;
  read_at: IsoDateTime | null;
}

/* ----------------------------------------------------------------- 实时通道 */

/**
 * WebSocket 事件（`WS /api/v1/ws/matches/{match_id}`）
 * ⚠️ `message.created` 的 data 只有 id 与 body，不含 sender_id / created_at
 */
export type WsServerEvent =
  | { type: "messages.snapshot"; data: [] }
  | { type: "message.created"; data: { id: Id; body: string } };

/* ==================================================================== */
/* 以下为「已实现但尚未迁移到 /api/v1」的 Agent 能力类型                    */
/* 当前挂在旧根路径（无鉴权）。迁移完成前请只在 legacy-agent.ts 里临时使用， */
/* 并在迁移后删除。映射表见 API-CONTRACT.md 第 4.2 节。                     */
/* ==================================================================== */

/** 待迁移：POST /api/v1/me/elicitations ← POST /users/{user_id}/elicit */
export interface OptionOut {
  text: string;
  polarity: OptionPolarity;
}

export interface CardOut {
  elicitation_id: number;
  question: string;
  kind: string;
  options: OptionOut[];
  /** 期望信息增益（后端决定先问哪张卡用）。**不要**展示给用户，也不要换算成百分比 */
  expected_information_gain: number;
  evidence_weight: number;
}

export interface ElicitOut {
  user_id: number;
  /** 作答前的伯努利熵（0 ~ 0.6931） */
  belief_entropy_before: number;
  cards: CardOut[];
}

/** 待迁移：POST /api/v1/me/elicitations/{elicitation_id}/responses ← POST /users/{user_id}/respond */
export interface RespondIn {
  elicitation_id: number;
  choice: string;
  reaction_time_ms: number;
}

export interface RespondOut {
  user_id: number;
  hypothesis: string;
  choice: string;
  alpha: number;
  beta: number;
  belief_mean: number;
  entropy_before: number;
  entropy_after: number;
  /** 负值表示不确定性下降。只可用于"还在了解你"的可视化，禁止换算成百分比 */
  entropy_delta: number;
}

/** 待迁移：GET /api/v1/me/belief ← GET /users/{user_id}/belief */
export interface BeliefOut {
  user_id: number;
  hypothesis: string;
  alpha: number;
  beta: number;
  mean: number;
  /** α+β，证据量 */
  strength: number;
  /** 伯努利熵（0 ~ 0.6931），越小越确定 */
  entropy: number;
  ci_low: number;
  ci_high: number;
  responses_counted: number;
}

/** 待迁移：POST /api/v1/me/story ← POST /users/{user_id}/story */
export interface StoryOut {
  user_id: number;
  message: string;
  /** Your Story 文本（**不要**命名成"人格报告"） */
  story: string;
}

/** 待迁移：GET /api/v1/me/profile ← GET /users/{user_id}/profile */
export interface ProfileOut {
  user_id: number;
  summary: string;
  embedding_dims: number;
  source_hash: string;
  updated_at: IsoDateTime;
}

/** 待迁移：POST /api/v1/me/profile/refresh ← POST /users/{user_id}/profile/refresh?force= */
export interface ProfileRefreshOut {
  user_id: number;
  /** false 表示事件序列未变化、命中缓存 */
  updated: boolean;
  summary: string;
  summary_chars: number;
  embedding_dims: number;
}

export interface MatchNarrativeOut {
  /** 共同点 */
  shared: string[];
  /** 差异 */
  differences: string[];
  /** 罕见共同点 */
  rare_common: string[];
  /** 世界观差异 */
  worldviews: string[];
  /** 「为什么是这个人」整段叙事 */
  why_this_person: string;
}

/**
 * 待迁移：POST /api/v1/me/match-insights ← POST /users/{user_id}/match
 * 后端的 `score` 与 `match_uncertainty` 被显式 exclude，不会出现在 JSON 里
 */
export interface AgentMatchOut {
  user_id: number;
  matched_user_id: number;
  /** 当前用户信念的伯努利熵，越小越确定 */
  belief_entropy: number;
  narrative: MatchNarrativeOut;
  reasons: string[];
  explanation: string;
}

/** 待迁移：POST /api/v1/relationships/{candidate_id}/signals ← POST /relationships/{user_a}/{user_b}/signals */
export interface RelationshipSignalIn {
  source?: string;
  kind: string;
  content?: string;
  weight?: number;
}

export interface RelationshipPosteriorOut {
  relationship_id: number;
  user_a: number;
  user_b: number;
  alpha: number;
  beta: number;
  mean: number;
  entropy: number;
}

/* -------------------------------------------------------------------- 埋点 */

export type BehaviorEventType = "browse" | "dwell" | "like" | "swipe";

/** 待迁移：POST /api/v1/events ← POST /events */
export interface EventIn {
  user_id: number;
  event_type: BehaviorEventType;
  target_id?: string | null;
  duration_ms: number;
}

export interface EventsIn {
  events: EventIn[];
}

export interface EventsOut {
  inserted: number;
}

export interface EventOut {
  id: number;
  event_type: BehaviorEventType;
  target_id: string | null;
  duration_ms: number | null;
  created_at: IsoDateTime;
}

/** 待迁移：GET /api/v1/me/events ← GET /users/{user_id}/events?limit= */
export interface UserEventsOut {
  items: EventOut[];
}

/* ------------------------------------------------ UI 自查用常量（可选） */

/** 禁止出现在界面上的词（评审必查） */
export const PRODUCT_FORBIDDEN_WORDS = [
  "匹配度",
  "契合度",
  "相似度",
  "人格报告",
  "MBTI",
  "用户标签",
  "用户画像",
  "分数",
  "排名",
  "等级",
] as const;

/** 应当使用的替代表达 */
export const PRODUCT_REQUIRED_WORDS = [
  "Your Story",
  "How I See You",
  "共同点",
  "差异",
  "罕见共同点",
  "世界观差异",
] as const;
