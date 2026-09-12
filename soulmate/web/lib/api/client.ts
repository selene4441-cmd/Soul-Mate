/**
 * SoulMate Agent API —— 极简类型化客户端
 *
 * 基准：`soulmate` @ commit `e2d2401`，配套 `types.ts` 与 `docs/api/API-CONTRACT.md`
 *
 * 它负责三件容易写错的事：
 * 1. **同源代理**：默认打同源 `/api/proxy/v1`，不直连后端（后端无 CORS + SameSite=Lax）
 * 2. **CSRF 双提交**：非 GET/HEAD 自动带上 `X-CSRF-Token`（值取 cookie `tongpin_csrf`）
 * 3. **统一错误**：把 `ErrorEnvelope` 抛成 `ApiError`，`trace_id` 一起带出来便于上报
 *
 * 不引入任何依赖，可直接放进 Next.js 项目。
 */

import type {
  AuthOut,
  ClaimOut,
  ConsentIn,
  ConsentOut,
  ConsentScope,
  Id,
  InvitationIn,
  InvitationOut,
  LoginIn,
  MatchOut,
  MessageIn,
  MessageOut,
  QuestionnaireOut,
  QuestionnaireSubmissionIn,
  RecommendationsOut,
  RegisterIn,
  SpaceStateOut,
  UserOut,
  WsServerEvent,
} from "./types";

/**
 * 只声明这里用到的那一点环境变量，避免强制依赖 @types/node（模块作用域声明，不与全局冲突）。
 * 注意：下面必须保留 `process.env.NEXT_PUBLIC_*` 的**字面写法**，
 * Next.js 才能在客户端 bundle 里静态内联这些值。
 */
declare const process: { env: Record<string, string | undefined> };

/* ------------------------------------------------------------------ 基础 */

/** 同源代理前缀；想直连后端就设 NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000/api/v1（需后端开 CORS） */
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "/api/proxy/v1";

const CSRF_COOKIE = "tongpin_csrf";
const UNSAFE_METHODS = new Set(["POST", "PATCH", "DELETE", "PUT"]);

/** 读 JS 可读的 CSRF cookie（同源代理下读到的也是前端域的 cookie） */
export function readCsrfToken(): string | null {
  if (typeof document === "undefined") return null;
  const m = document.cookie.match(/(?:^|;\s*)tongpin_csrf=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : null;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly traceId: string;
  readonly details: Record<string, unknown>;

  constructor(opts: { status: number; code: string; message: string; traceId: string; details?: Record<string, unknown> }) {
    super(opts.message);
    this.name = "ApiError";
    this.status = opts.status;
    this.code = opts.code;
    this.traceId = opts.traceId;
    this.details = opts.details ?? {};
  }

  /** 未登录 / session 过期 → 前端应跳登录页并清空本地态 */
  get isUnauthorized(): boolean {
    return this.status === 401;
  }

  /** 缺少授权 scope → 走"说明用途 → 用户同意 → POST /consents"流程 */
  get isConsentRequired(): boolean {
    return this.code === "CONSENT_REQUIRED";
  }

  /**
   * CSRF 失败几乎总是前端漏带头部，**不要提示用户**。
   * 拿不到 token 通常意味着用户还没登录（或 cookie 被清了）。
   */
  get isCsrfInvalid(): boolean {
    return this.code === "CSRF_INVALID";
  }

  get isRateLimited(): boolean {
    // ⚠️ 后端 429 的 code 目前是通用的 HTTP_ERROR，所以按状态码判断
    return this.status === 429;
  }
}

/* ------------------------------------------------------------------ 请求 */

export interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  signal?: AbortSignal;
  /** 401 时的统一回调（跳登录、清 store 之类），避免每个调用点各写一遍 */
  onUnauthorized?: () => void;
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = options.method ?? "GET";
  const headers: Record<string, string> = { Accept: "application/json" };

  if (options.body !== undefined) headers["Content-Type"] = "application/json; charset=utf-8";

  if (UNSAFE_METHODS.has(method)) {
    const token = readCsrfToken();
    if (token) headers["X-CSRF-Token"] = token;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    credentials: "include",
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    signal: options.signal,
  });

  if (res.status === 204) return undefined as T;

  const text = await res.text();
  const parsed: unknown = text ? safeJson(text) : undefined;

  if (!res.ok) {
    const envelope = (parsed ?? {}) as Partial<{ code: string; message: string; trace_id: string; details: Record<string, unknown> }>;
    const err = new ApiError({
      status: res.status,
      code: envelope.code ?? "HTTP_ERROR",
      message: envelope.message ?? res.statusText ?? "请求失败",
      traceId: envelope.trace_id ?? res.headers.get("X-Trace-Id") ?? "",
      details: envelope.details ?? {},
    });
    if (err.isUnauthorized) options.onUnauthorized?.();
    throw err;
  }

  return parsed as T;
}

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return undefined;
  }
}

/* -------------------------------------------------------------- 领域封装 */

export const authApi = {
  register: (body: RegisterIn) => apiFetch<AuthOut>("/auth/register", { method: "POST", body }),
  login: (body: LoginIn) => apiFetch<AuthOut>("/auth/login", { method: "POST", body }),
  logout: () => apiFetch<{ status: string }>("/auth/logout", { method: "POST" }),
  /** 会话探测：401 即未登录（不需要额外接口） */
  me: (onUnauthorized?: () => void) => apiFetch<UserOut>("/auth/me", { onUnauthorized }),
};

export const consentApi = {
  list: () => apiFetch<ConsentOut[]>("/consents"),
  grant: (body: ConsentIn) => apiFetch<ConsentOut>("/consents", { method: "POST", body }),
  /** 是否已授予某 scope。涉及匹配/聊天的动作前都该先查，不要靠本地缓存猜 */
  async has(scope: ConsentScope): Promise<boolean> {
    const rows = await consentApi.list();
    return rows.some((r) => r.scope === scope);
  },
};

export const questionnaireApi = {
  get: () => apiFetch<QuestionnaireOut>("/questionnaire"),
  submit: (body: QuestionnaireSubmissionIn, onUnauthorized?: () => void) =>
    apiFetch<ClaimOut[]>("/questionnaire/submissions", { method: "POST", body, onUnauthorized }),
};

export const claimApi = {
  list: (onUnauthorized?: () => void) => apiFetch<ClaimOut[]>("/claims", { onUnauthorized }),
};

export const spaceApi = {
  /** 驱动前端路由；不要自己推断状态 */
  state: (onUnauthorized?: () => void) => apiFetch<SpaceStateOut>("/space/state", { onUnauthorized }),
};

export const recommendationApi = {
  /** 生成推荐。注意：响应没有任何分数字段，返回顺序即排序 */
  generate: () => apiFetch<RecommendationsOut>("/recommendations", { method: "POST" }),
  /** ⚠️ candidate_id 在这里是数字 */
  get: (candidateId: number) => apiFetch<RecommendationsOut>(`/recommendations/${candidateId}`),
};

export const invitationApi = {
  /** 双向即成 match；只有 connected 才能发消息 */
  create: (body: InvitationIn) => apiFetch<InvitationOut>("/invitations", { method: "POST", body }),
};

export const matchApi = {
  list: (onUnauthorized?: () => void) => apiFetch<MatchOut[]>("/matches", { onUnauthorized }),
  messages: (matchId: Id) => apiFetch<MessageOut[]>(`/matches/${matchId}/messages`),
  /** client_message_id 幂等：重试安全，同值返回同一条 */
  send: (matchId: Id, body: MessageIn) =>
    apiFetch<MessageOut>(`/matches/${matchId}/messages`, { method: "POST", body }),
};

/* -------------------------------------------------------------- WebSocket */

/** 直连后端（Route Handler 不支持 WS 升级）。生产环境应由反向代理转发升级请求 */
export function matchSocketUrl(matchId: Id): string {
  const explicit = process.env.NEXT_PUBLIC_WS_BASE;
  if (explicit) return `${explicit}/api/v1/ws/matches/${matchId}`;
  if (typeof window === "undefined") return "";
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  // 默认指向本机后端；换环境时设 NEXT_PUBLIC_WS_BASE
  return `${proto}//127.0.0.1:8000/api/v1/ws/matches/${matchId}`;
}

export interface MatchSocketHandlers {
  /** 收到 messages.snapshot（data 恒为空数组）→ 清空本地消息列表 */
  onSnapshot?: (data: []) => void;
  /** 收到 message.created → 按 id 去重后追加；自己刚发出的消息（同 id）直接跳过 */
  onMessage?: (msg: { id: Id; body: string }) => void;
  /** 4401 未登录 / 4403 不属于该 match */
  onClose?: (code: number, reason: string) => void;
  onError?: (event: Event) => void;
}

export function openMatchSocket(matchId: Id, handlers: MatchSocketHandlers): WebSocket | null {
  const url = matchSocketUrl(matchId);
  if (!url) return null;

  const ws = new WebSocket(url);
  const seen = new Set<string>();

  ws.onmessage = (event: MessageEvent<string>) => {
    let payload: WsServerEvent;
    try {
      payload = JSON.parse(event.data) as WsServerEvent;
    } catch {
      return;
    }
    if (payload.type === "messages.snapshot") {
      seen.clear();
      handlers.onSnapshot?.(payload.data);
      return;
    }
    if (payload.type === "message.created") {
      if (seen.has(payload.data.id)) return; // 历史回放 + 自己 POST 成功会有重复
      seen.add(payload.data.id);
      handlers.onMessage?.(payload.data);
    }
  };

  ws.onclose = (event) => handlers.onClose?.(event.code, event.reason);
  ws.onerror = (event) => handlers.onError?.(event);
  return ws;
}
