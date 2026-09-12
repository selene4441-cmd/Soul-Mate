"use client";

/**
 * 前端请求封装（与上传的 apps/web/lib/api.ts 同一套接口形态，便于互相搬运）。
 *
 * - 默认走同源代理 `/api/proxy/v1`（浏览器不能直连后端：无 CORS + SameSite=Lax）
 * - 非 GET/HEAD/OPTIONS 自动带 `X-CSRF-Token`（值取 cookie `tongpin_csrf`）
 * - 失败统一抛 ApiError，带 code / trace_id / details
 */

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "/api/proxy/v1";

export class ApiError extends Error {
  status: number;
  code: string;
  traceId?: string;
  details?: unknown;

  constructor(message: string, status: number, code: string, traceId?: string, details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.traceId = traceId;
    this.details = details;
  }

  /** 未登录 / session 过期 */
  get isUnauthorized(): boolean {
    return this.status === 401;
  }

  /** 缺少授权 scope（details.scope 指出缺哪个） */
  get isConsentRequired(): boolean {
    return this.code === "CONSENT_REQUIRED";
  }

  /** CSRF 失败几乎总是前端漏带头部，不要提示用户 */
  get isCsrfInvalid(): boolean {
    return this.code === "CSRF_INVALID";
  }

  get isRateLimited(): boolean {
    return this.status === 429;
  }
}

export function csrfToken(): string {
  if (typeof document === "undefined") return "";
  const match = document.cookie.split("; ").find((item) => item.startsWith("tongpin_csrf="));
  return match ? decodeURIComponent(match.split("=").slice(1).join("=")) : "";
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? "GET").toUpperCase();
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    headers.set("X-CSRF-Token", csrfToken());
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
    credentials: "include",
    cache: "no-store",
  });

  if (response.status === 204) return undefined as T;

  const body = await response.json().catch(() => null);

  if (!response.ok) {
    throw new ApiError(
      body?.message ?? "请求未完成，请稍后重试。",
      response.status,
      body?.code ?? "REQUEST_FAILED",
      body?.trace_id ?? response.headers.get("X-Trace-Id") ?? undefined,
      body?.details,
    );
  }

  return body as T;
}

export function postJson<T>(path: string, body?: unknown): Promise<T> {
  return apiFetch<T>(path, {
    method: "POST",
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

export function patchJson<T>(path: string, body: unknown): Promise<T> {
  return apiFetch<T>(path, { method: "PATCH", body: JSON.stringify(body) });
}

/** 把任意异常转成一句可展示的文案（带 trace_id，便于反馈） */
export function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.isUnauthorized) return "登录状态已失效，请重新登录。";
    if (error.isCsrfInvalid) return "请求被安全校验拒绝（前端缺少 CSRF 令牌），请刷新页面重试。";
    if (error.isRateLimited) return "操作太频繁了，请稍等一会儿再试。";
    if (error.isConsentRequired) return "需要先授权后才能继续。";
    const trace = error.traceId ? `（trace_id: ${error.traceId}）` : "";
    return `${error.message}${trace}`;
  }
  if (error instanceof Error) return error.message;
  return "发生未知错误。";
}
