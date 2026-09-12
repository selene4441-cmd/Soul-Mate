/**
 * 同源代理：把浏览器发往 `/api/proxy/v1/*` 的请求转发到后端 `/api/v1/*`。
 *
 * 为什么要它：后端没有配 CORS，且 session cookie 是 `SameSite=Lax`，
 * 浏览器直连后端会预检失败 / cookie 不生效。走同源代理后 cookie 与 CSRF 都留在前端域内。
 *
 * 放置路径（必须一致）：`app/api/proxy/v1/[...path]/route.ts`
 * 环境变量：`API_BASE_URL`（默认 `http://127.0.0.1:8000`）
 *
 * ⚠️ WebSocket 不能走这里（Route Handler 不支持 WS 升级）。聊天实时通道要么直连后端，
 *    要么在生产环境由 Nginx/Caddy 转发升级请求。见 `lib/api/client.ts` 的 `matchSocketUrl`。
 */

export const dynamic = "force-dynamic";

/** 只声明用到的那一点环境变量，避免强制依赖 @types/node */
declare const process: { env: Record<string, string | undefined> };

const BACKEND = process.env.API_BASE_URL ?? "http://127.0.0.1:8000";

/** 只转发必要请求头；Host / Origin 交给 fetch 自己决定，不要手工带 */
const REQUEST_HEADERS = ["cookie", "content-type", "x-csrf-token", "accept", "accept-language"];
const RESPONSE_HEADERS = ["content-type", "x-trace-id", "cache-control"];

/**
 * 逐条取出 Set-Cookie。
 * 注意：`Headers.get("set-cookie")` 会把多个 cookie 合并成一条字符串，直接用会导致
 * 只有第一个 cookie 生效（这是最常见的"登录成功但下一个请求还是 401"的原因）。
 */
function getSetCookies(headers: Headers): string[] {
  const withGetter = headers as Headers & { getSetCookie?: () => string[] };
  if (typeof withGetter.getSetCookie === "function") {
    return withGetter.getSetCookie();
  }
  const raw = headers.get("set-cookie");
  if (!raw) return [];
  return raw
    .split(/,(?=[^;,]+=)/g)
    .map((part) => part.trim())
    .filter(Boolean);
}

async function forward(req: Request, segments: string[]): Promise<Response> {
  const incoming = new URL(req.url);
  const target = `${BACKEND}/api/v1/${segments.join("/")}${incoming.search}`;

  const headers = new Headers();
  for (const key of REQUEST_HEADERS) {
    const value = req.headers.get(key);
    if (value) headers.set(key, value);
  }

  const hasBody = req.method !== "GET" && req.method !== "HEAD";
  const upstream = await fetch(target, {
    method: req.method,
    headers,
    body: hasBody ? await req.arrayBuffer() : undefined,
    redirect: "manual",
  });

  const out = new Headers();
  for (const key of RESPONSE_HEADERS) {
    const value = upstream.headers.get(key);
    if (value) out.set(key, value);
  }
  for (const cookie of getSetCookies(upstream.headers)) {
    out.append("set-cookie", cookie);
  }

  return new Response(upstream.body, { status: upstream.status, headers: out });
}

type RouteContext = { params: { path: string[] } };

export async function GET(req: Request, ctx: RouteContext): Promise<Response> {
  return forward(req, ctx.params.path);
}

export async function POST(req: Request, ctx: RouteContext): Promise<Response> {
  return forward(req, ctx.params.path);
}

export async function PATCH(req: Request, ctx: RouteContext): Promise<Response> {
  return forward(req, ctx.params.path);
}

export async function PUT(req: Request, ctx: RouteContext): Promise<Response> {
  return forward(req, ctx.params.path);
}

export async function DELETE(req: Request, ctx: RouteContext): Promise<Response> {
  return forward(req, ctx.params.path);
}
