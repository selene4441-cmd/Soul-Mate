"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { ApiError, apiFetch, postJson } from "@/lib/api";

type Match = {
  id: string;
  other_user: { id: string; display_name: string };
  status: string;
  created_at: string;
};
type Message = {
  id: string;
  conversation_id: string;
  sender_id: string;
  body: string;
  client_message_id: string;
  created_at: string;
  read_at: string | null;
};

export default function MessagesPage() {
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<string | null>(null);
  const [body, setBody] = useState("");
  const [error, setError] = useState("");
  const matches = useQuery({ queryKey: ["matches"], queryFn: () => apiFetch<Match[]>("/matches") });

  useEffect(() => {
    if (!selected && matches.data?.length) setSelected(matches.data[0].id);
  }, [matches.data, selected]);

  const messages = useQuery({
    queryKey: ["messages", selected],
    queryFn: () => apiFetch<Message[]>(`/matches/${selected}/messages`),
    enabled: Boolean(selected),
    refetchInterval: 5000,
  });

  useEffect(() => {
    if (!selected) return;
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const socket = new WebSocket(`${protocol}//${window.location.host}/api/v1/ws/matches/${selected}`);
    socket.onmessage = (event) => {
      const payload = JSON.parse(event.data) as { type: string; data?: Message[] | Message };
      if (payload.type === "messages.snapshot" && Array.isArray(payload.data)) {
        queryClient.setQueryData(["messages", selected], payload.data);
      }
      if (payload.type === "message.created" && payload.data && !Array.isArray(payload.data)) {
        const incoming = payload.data;
        queryClient.setQueryData<Message[]>(["messages", selected], (previous = []) => {
          if (previous.some((item) => item.id === incoming.id)) return previous;
          return [...previous, incoming];
        });
      }
    };
    return () => socket.close();
  }, [queryClient, selected]);

  const send = useMutation({
    mutationFn: () =>
      postJson<Message>(`/matches/${selected}/messages`, {
        body,
        client_message_id: crypto.randomUUID(),
      }),
    onSuccess: async () => {
      setBody("");
      setError("");
      await queryClient.invalidateQueries({ queryKey: ["messages", selected] });
    },
    onError: (reason) => setError(reason instanceof ApiError ? reason.message : "消息未发送成功。"),
  });

  return (
    <div className="pb-20">
      <div className="mb-7">
        <p className="eyebrow">双向交流</p>
        <h1 className="mt-3 text-3xl font-semibold sm:text-4xl">从具体情境继续了解</h1>
        <p className="muted mt-3 max-w-2xl leading-7">
          消息先写入服务端再显示。交流只对已经确认连接的人开放，你可以随时停止并反馈安全问题。
        </p>
      </div>

      {!matches.data?.length ? (
        <section className="panel">
          <h2 className="text-xl font-semibold">还没有开启交流</h2>
          <p className="muted mt-3">先从一组关系线索里选择愿意继续了解的人。</p>
        </section>
      ) : (
        <div className="grid min-h-[32rem] overflow-hidden rounded-[1.75rem] border border-[var(--line)] bg-white/70 lg:grid-cols-[18rem_1fr]">
          <aside className="border-b border-[var(--line)] p-3 lg:border-b-0 lg:border-r">
            {matches.data.map((match) => (
              <button
                key={match.id}
                type="button"
                onClick={() => setSelected(match.id)}
                className={`mb-2 w-full rounded-2xl p-4 text-left ${
                  selected === match.id ? "bg-[var(--moss)] text-white" : "hover:bg-[#f2f0e8]"
                }`}
              >
                <strong>{match.other_user.display_name}</strong>
                <span className={`mt-1 block text-xs ${selected === match.id ? "text-white/75" : "muted"}`}>
                  交流已开启
                </span>
              </button>
            ))}
          </aside>
          <section className="flex min-h-[32rem] flex-col">
            <div className="flex-1 space-y-3 overflow-y-auto p-5" aria-live="polite">
              {messages.data?.map((message) => (
                <article key={message.id} className="max-w-[85%] rounded-2xl bg-[#f0eee5] px-4 py-3">
                  <p className="leading-6">{message.body}</p>
                  <time className="muted mt-2 block text-xs">
                    {new Date(message.created_at).toLocaleString("zh-CN", { hour12: false })}
                  </time>
                </article>
              ))}
              {!messages.data?.length ? <p className="muted text-sm">可以从一个具体场景开始，不必一次说很多。</p> : null}
            </div>
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
                  placeholder="写下想确认的具体情境…"
                />
                <button className="button-primary" disabled={!body.trim() || send.isPending}>
                  {send.isPending ? "发送中" : "发送"}
                </button>
              </div>
              {error ? <p className="mt-3 text-sm text-[var(--clay)]">{error}</p> : null}
            </form>
          </section>
        </div>
      )}
    </div>
  );
}
