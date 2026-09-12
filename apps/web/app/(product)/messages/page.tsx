"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { ApiError, apiFetch, postJson } from "@/lib/api";
import { useMe } from "@/lib/auth";

type Conversation = {
  id: string;
  match_id: string;
  other_user: { id: string; display_name: string };
  status: string;
  context_snapshot: {
    headline?: string;
    common_signals?: string[];
    differences?: string[];
    unknowns?: string[];
  };
  active_cue: { id: string; cue_type: string; text: string; created_by: string } | null;
  unread_count: number;
  opened_at: string;
  last_message_at: string | null;
};

type Message = {
  id: string;
  conversation_id: string;
  sender_id: string;
  body: string;
  client_message_id: string;
  kind: string;
  reply_to_id: string | null;
  created_at: string;
  read_at: string | null;
};

type MessagePage = {
  items: Message[];
  next_cursor: string | null;
};

export default function MessagesPage() {
  const queryClient = useQueryClient();
  const { data: me } = useMe();
  const [selected, setSelected] = useState<string | null>(null);
  const [body, setBody] = useState("");
  const [error, setError] = useState("");
  const conversations = useQuery({
    queryKey: ["conversations"],
    queryFn: () => apiFetch<Conversation[]>("/conversations"),
  });

  useEffect(() => {
    if (!selected && conversations.data?.length) setSelected(conversations.data[0].id);
  }, [conversations.data, selected]);

  const active = conversations.data?.find((item) => item.id === selected) ?? null;
  const messages = useQuery({
    queryKey: ["messages", selected],
    queryFn: () => apiFetch<MessagePage>(`/conversations/${selected}/messages?limit=100`),
    enabled: Boolean(selected),
    refetchInterval: 5000,
  });

  useEffect(() => {
    if (!selected) return;
    void apiFetch(`/conversations/${selected}/read`, { method: "POST" }).catch(() => undefined);
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const socket = new WebSocket(`${protocol}//${window.location.host}/api/v1/ws/conversations/${selected}`);
    socket.onmessage = (event) => {
      const payload = JSON.parse(event.data) as { type: string; data?: Message[] | Message };
      if (payload.type === "messages.snapshot" && Array.isArray(payload.data)) {
        queryClient.setQueryData<MessagePage>(["messages", selected], {
          items: payload.data,
          next_cursor: null,
        });
      }
      if (payload.type === "message.created" && payload.data && !Array.isArray(payload.data)) {
        const incoming = payload.data;
        queryClient.setQueryData<MessagePage>(
          ["messages", selected],
          (previous = { items: [], next_cursor: null }) => {
            if (previous.items.some((item) => item.id === incoming.id)) return previous;
            return { ...previous, items: [...previous.items, incoming] };
          },
        );
      }
    };
    return () => socket.close();
  }, [queryClient, selected]);

  const send = useMutation({
    mutationFn: () =>
      postJson<Message>(`/conversations/${selected}/messages`, {
        body,
        client_message_id: crypto.randomUUID(),
        kind: "text",
      }),
    onSuccess: async () => {
      setBody("");
      setError("");
      await queryClient.invalidateQueries({ queryKey: ["messages", selected] });
    },
    onError: (reason) => setError(reason instanceof ApiError ? reason.message : "消息未发送成功。"),
  });

  const closeConversation = useMutation({
    mutationFn: () => postJson(`/conversations/${selected}/close`, { reason: "not_a_fit" }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["conversations"] });
      await queryClient.invalidateQueries({ queryKey: ["messages", selected] });
    },
    onError: (reason) =>
      setError(reason instanceof ApiError ? reason.message : "暂时无法结束交流。"),
  });

  const blockUser = useMutation({
    mutationFn: () =>
      postJson(`/blocks`, {
        blocked_user_id: active?.other_user.id,
        reason_private: null,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["conversations"] });
      await queryClient.invalidateQueries({ queryKey: ["messages", selected] });
    },
    onError: (reason) =>
      setError(reason instanceof ApiError ? reason.message : "暂时无法完成拉黑。"),
  });

  const reportUser = useMutation({
    mutationFn: (details: string) =>
      postJson(`/safety/reports`, {
        subject_id: active?.other_user.id,
        conversation_id: selected,
        message_id: messages.data?.items.at(-1)?.id ?? null,
        event_type: "other",
        severity: "high",
        details: details || null,
      }),
    onSuccess: () => setError("举报已提交，平台会在受控流程中处理。"),
    onError: (reason) =>
      setError(reason instanceof ApiError ? reason.message : "暂时无法提交举报。"),
  });

  return (
    <div className="pb-20">
      <div className="mb-7">
        <p className="eyebrow">双向交流</p>
        <h1 className="mt-3 text-3xl font-semibold sm:text-4xl">从具体情境继续了解</h1>
        <p className="muted mt-3 max-w-2xl leading-7">
          交流只对已经确认连接的人开放。你可以随时结束交流或拉黑，不需要向对方解释。
        </p>
      </div>

      {!conversations.data?.length ? (
        <section className="panel">
          <h2 className="text-xl font-semibold">还没有开启交流</h2>
          <p className="muted mt-3 leading-7">
            先从一组关系线索里选择一个愿意继续确认的具体情境。
          </p>
        </section>
      ) : (
        <div className="grid min-h-[36rem] overflow-hidden rounded-[1.75rem] border border-[var(--line)] bg-white/70 lg:grid-cols-[18rem_1fr]">
          <aside className="border-b border-[var(--line)] p-3 lg:border-b-0 lg:border-r">
            {conversations.data.map((conversation) => (
              <button
                key={conversation.id}
                type="button"
                onClick={() => setSelected(conversation.id)}
                className={`mb-2 w-full rounded-2xl p-4 text-left ${
                  selected === conversation.id ? "bg-[var(--moss)] text-white" : "hover:bg-[#f2f0e8]"
                }`}
              >
                <span className="font-semibold">{conversation.other_user.display_name}</span>
                <span
                  className={`mt-1 block text-xs ${
                    selected === conversation.id ? "text-white/75" : "muted"
                  }`}
                >
                  {conversation.status === "active"
                    ? conversation.active_cue?.text ?? "交流已开启"
                    : "交流已经结束"}
                </span>
                {conversation.unread_count > 0 ? (
                  <span className="mt-2 inline-block rounded-full bg-[var(--clay)] px-2 py-1 text-xs text-white">
                    {conversation.unread_count} 条新消息
                  </span>
                ) : null}
              </button>
            ))}
          </aside>

          <section className="flex min-h-[36rem] flex-col">
            {active ? (
              <>
                <header className="border-b border-[var(--line)] p-5">
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div>
                      <p className="eyebrow">当前交流</p>
                      <h2 className="mt-2 text-xl font-semibold">{active.other_user.display_name}</h2>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {active.status === "active" ? (
                        <>
                          <button
                            className="chip"
                            onClick={() => {
                              if (window.confirm("确认结束这次交流吗？双方将不能继续发送消息。")) {
                                closeConversation.mutate();
                              }
                            }}
                          >
                            结束交流
                          </button>
                          <button
                            className="chip"
                            onClick={() => {
                              if (window.confirm("确认拉黑吗？现行交流会立即停止。")) {
                                blockUser.mutate();
                              }
                            }}
                          >
                            拉黑
                          </button>
                          <button
                            className="chip"
                            onClick={() => {
                              const details = window.prompt("请简要说明需要平台处理的情况。");
                              if (details !== null) reportUser.mutate(details);
                            }}
                          >
                            举报
                          </button>
                        </>
                      ) : (
                        <span className="chip">交流已结束</span>
                      )}
                    </div>
                  </div>
                  {active.active_cue ? (
                    <div className="mt-4 rounded-2xl bg-[rgba(46,107,87,0.07)] p-4">
                      <p className="text-xs font-semibold text-[var(--moss)]">交流提示 · 系统议题</p>
                      <p className="mt-2 leading-7">{active.active_cue.text}</p>
                    </div>
                  ) : null}
                  <ContextSummary context={active.context_snapshot} />
                </header>

                <div className="flex-1 space-y-3 overflow-y-auto p-5" aria-live="polite">
                  {messages.data?.items.map((message) => {
                    const mine = message.sender_id === me?.id;
                    return (
                      <article
                        key={message.id}
                        className={`max-w-[85%] rounded-2xl px-4 py-3 ${
                          mine
                            ? "ml-auto bg-[var(--moss)] text-white"
                            : "bg-[#f0eee5] text-[var(--ink)]"
                        }`}
                      >
                        <p className="leading-6">{message.body}</p>
                        <time className={`mt-2 block text-xs ${mine ? "text-white/70" : "muted"}`}>
                          {new Date(message.created_at).toLocaleString("zh-CN", {
                            hour12: false,
                          })}
                        </time>
                      </article>
                    );
                  })}
                  {!messages.data?.items.length ? (
                    <p className="muted text-sm">
                      可以从上面的交流提示开始，不必一次说很多。系统提示不是对方发来的消息。
                    </p>
                  ) : null}
                </div>

                {active.status === "active" ? (
                  <form
                    className="border-t border-[var(--line)] p-4"
                    onSubmit={(event) => {
                      event.preventDefault();
                      if (body.trim()) send.mutate();
                    }}
                  >
                    <div className="flex items-end gap-3">
                      <textarea
                        className="field min-h-20 resize-none"
                        value={body}
                        onChange={(event) => setBody(event.target.value)}
                        maxLength={2000}
                        placeholder="回应这个情境，或确认一件具体的事…"
                      />
                      <button className="button-primary" disabled={!body.trim() || send.isPending}>
                        {send.isPending ? "发送中" : "发送"}
                      </button>
                    </div>
                    {error ? <p className="mt-3 text-sm text-[var(--clay)]">{error}</p> : null}
                  </form>
                ) : (
                  <p className="border-t border-[var(--line)] p-5 text-sm text-[var(--clay)]">
                    交流已经结束，输入区已关闭。
                  </p>
                )}
              </>
            ) : null}
          </section>
        </div>
      )}
    </div>
  );
}

function ContextSummary({
  context,
}: {
  context: Conversation["context_snapshot"];
}) {
  const rows = [
    ["共同点", context.common_signals],
    ["可能需要确认", context.differences],
    ["仍然不知道", context.unknowns],
  ] as const;
  return (
    <details className="mt-4 text-sm">
      <summary className="muted cursor-pointer">查看开启交流时的关系线索</summary>
      <div className="mt-3 grid gap-3 md:grid-cols-3">
        {rows.map(([title, items]) =>
          items?.length ? (
            <div key={title} className="signal-card">
              <p className="font-semibold">{title}</p>
              <ul className="muted mt-2 space-y-2 text-xs leading-5">
                {items.slice(0, 2).map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          ) : null,
        )}
      </div>
    </details>
  );
}
