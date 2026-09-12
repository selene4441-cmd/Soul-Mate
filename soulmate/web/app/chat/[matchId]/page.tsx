"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { apiFetch, describeError, postJson } from "../../../lib/api";
import type { MessageOut, UserOut, WsServerEvent } from "../../../lib/api/types";

type WsState = "connecting" | "open" | "closed" | "unauthorized" | "forbidden";

export default function ChatPage({ params }: { params: { matchId: string } }) {
  const matchId = params.matchId;

  const [me, setMe] = useState<UserOut | null>(null);
  const [messages, setMessages] = useState<MessageOut[]>([]);
  const [text, setText] = useState("");
  const [wsState, setWsState] = useState<WsState>("connecting");
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const listRef = useRef<HTMLDivElement | null>(null);
  const seenRef = useRef<Set<string>>(new Set());

  const loadMessages = useCallback(async () => {
    const rows = await apiFetch<MessageOut[]>(`/matches/${matchId}/messages`);
    seenRef.current = new Set(rows.map((r) => r.id));
    setMessages(rows);
  }, [matchId]);

  useEffect(() => {
    void (async () => {
      try {
        setMe(await apiFetch<UserOut>("/auth/me"));
        await loadMessages();
      } catch (err) {
        setError(describeError(err));
      }
    })();
  }, [loadMessages]);

  // WebSocket：直连后端（Route Handler 不支持 WS 升级）。
  // 主机名必须和页面一致，cookie 才带得过去（cookie 区分主机、不区分端口）。
  useEffect(() => {
    if (typeof window === "undefined") return;
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const explicit = process.env.NEXT_PUBLIC_WS_BASE;
    const backendOrigin = process.env.NEXT_PUBLIC_BACKEND_ORIGIN;

    let url: string;
    if (explicit) {
      url = `${explicit}/api/v1/ws/matches/${matchId}`;
    } else if (backendOrigin) {
      // 后端可能不在 8000（例如被别的服务占用时），用环境变量指定，只替换协议
      const wsOrigin = backendOrigin.replace(/^http/, "ws").replace(/\/$/, "");
      url = `${wsOrigin}/api/v1/ws/matches/${matchId}`;
    } else {
      url = `${proto}//${window.location.hostname}:8000/api/v1/ws/matches/${matchId}`;
    }

    let socket: WebSocket;
    try {
      socket = new WebSocket(url);
    } catch {
      setWsState("closed");
      return;
    }

    socket.onopen = () => setWsState("open");

    socket.onmessage = (event: MessageEvent<string>) => {
      let payload: WsServerEvent;
      try {
        payload = JSON.parse(event.data) as WsServerEvent;
      } catch {
        return;
      }
      if (payload.type === "messages.snapshot") {
        seenRef.current = new Set();
        setMessages([]);
        return;
      }
      if (payload.type === "message.created") {
        if (seenRef.current.has(payload.data.id)) return;
        seenRef.current.add(payload.data.id);
        // 事件体只有 id 与 body，缺 sender_id / created_at，所以重新拉一次完整列表
        void loadMessages().catch(() => undefined);
      }
    };

    socket.onclose = (event) => {
      if (event.code === 4401) setWsState("unauthorized");
      else if (event.code === 4403) setWsState("forbidden");
      else setWsState("closed");
    };

    socket.onerror = () => setWsState("closed");

    return () => socket.close();
  }, [matchId, loadMessages]);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
  }, [messages.length]);

  const canSend = useMemo(() => text.trim().length > 0 && !sending, [text, sending]);

  async function send() {
    const body = text.trim();
    if (!body) return;
    setSending(true);
    setError(null);
    try {
      const clientMessageId =
        typeof crypto !== "undefined" && "randomUUID" in crypto
          ? crypto.randomUUID()
          : `demo-${Date.now()}`;
      const created = await postJson<MessageOut>(`/matches/${matchId}/messages`, {
        body,
        client_message_id: clientMessageId
      });
      setText("");
      if (!seenRef.current.has(created.id)) {
        seenRef.current.add(created.id);
        setMessages((prev) => [...prev, created]);
      }
    } catch (err) {
      setError(describeError(err));
    } finally {
      setSending(false);
    }
  }

  const wsLabel: Record<WsState, string> = {
    connecting: "正在连接实时通道…",
    open: "实时通道已连接",
    closed: "实时通道未连接（可手动刷新）",
    unauthorized: "实时通道认证失败，请重新登录",
    forbidden: "你不属于这个会话"
  };

  return (
    <main className="container">
      <div className="row">
        <div>
          <div className="h1">聊天</div>
          <div className="muted mt4" style={{ fontSize: 12 }}>
            会话 {matchId.slice(0, 12)}… · {wsLabel[wsState]}
          </div>
        </div>
        <Link className="navBtn" style={{ width: "auto" }} href="/matches">
          返回
        </Link>
      </div>

      {error ? <div className="banner bannerError">{error}</div> : null}

      <div className="card">
        <div className="chatList" ref={listRef}>
          {messages.length === 0 ? (
            <div className="muted">还没有消息。可以从一个具体的生活场景开始。</div>
          ) : (
            messages.map((message) => {
              const mine = me !== null && message.sender_id === me.id;
              return (
                <div key={message.id} className={mine ? "bubble bubbleMine" : "bubble bubbleOther"}>
                  <div>{message.body}</div>
                  <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>
                    {mine ? "我" : "对方"} · {new Date(message.created_at).toLocaleString()}
                  </div>
                </div>
              );
            })
          )}
        </div>

        <div className="btnRow">
          <button className="btn" disabled={sending} onClick={() => void loadMessages().catch((e) => setError(describeError(e)))}>
            刷新消息
          </button>
          <button
            className="btn"
            onClick={() => setText("最近有什么小事让你觉得生活变好了？")}
          >
            用一句问候
          </button>
        </div>

        <div style={{ display: "flex", gap: 10, marginTop: 12 }}>
          <input
            className="input full"
            style={{ flex: 1 }}
            value={text}
            placeholder="写一句真心的话…"
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && canSend) void send();
            }}
          />
          <button className="btn btnPrimary" style={{ flex: "0 0 96px" }} disabled={!canSend} onClick={() => void send()}>
            {sending ? "发送中" : "发送"}
          </button>
        </div>
      </div>
    </main>
  );
}
