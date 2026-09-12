"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { ApiError, apiFetch, postJson } from "@/lib/api";

type ConnectionRequest = {
  id: string;
  direction: "incoming" | "outgoing";
  other_user: { id: string; display_name: string };
  status: string;
  cue_type: string;
  topic_text: string;
  personal_message: string | null;
  context_snapshot: {
    common_signals?: string[];
    differences?: string[];
    unknowns?: string[];
  };
  expires_at: string;
};

export default function RequestsPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [error, setError] = useState("");
  const incoming = useQuery({
    queryKey: ["connection-requests", "incoming"],
    queryFn: () =>
      apiFetch<ConnectionRequest[]>("/connection-requests?direction=incoming&status=pending"),
    refetchInterval: 5000,
  });
  const outgoing = useQuery({
    queryKey: ["connection-requests", "outgoing"],
    queryFn: () =>
      apiFetch<ConnectionRequest[]>("/connection-requests?direction=outgoing&status=pending"),
    refetchInterval: 5000,
  });

  const accept = useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/connection-requests/${id}/accept`, {
        method: "POST",
        headers: { "Idempotency-Key": crypto.randomUUID() },
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["connection-requests"] });
      await queryClient.invalidateQueries({ queryKey: ["conversations"] });
      router.push("/messages");
    },
    onError: (reason) =>
      setError(reason instanceof ApiError ? reason.message : "暂时无法接受请求。"),
  });

  const decline = useMutation({
    mutationFn: (id: string) => postJson(`/connection-requests/${id}/decline`, {}),
    onSuccess: async () => {
      setError("");
      await queryClient.invalidateQueries({ queryKey: ["connection-requests"] });
    },
    onError: (reason) =>
      setError(reason instanceof ApiError ? reason.message : "暂时无法处理请求。"),
  });

  const cancel = useMutation({
    mutationFn: (id: string) => apiFetch(`/connection-requests/${id}`, { method: "DELETE" }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["connection-requests"] });
    },
  });

  return (
    <div className="pb-20">
      <div className="mb-7">
        <p className="eyebrow">双向连接</p>
        <h1 className="mt-3 text-3xl font-semibold sm:text-4xl">先确认是否愿意聊聊</h1>
        <p className="muted mt-3 max-w-2xl leading-7">
          接受前不会开启会话。拒绝、撤回和结束都不需要向对方解释。
        </p>
      </div>

      {error ? <p className="mb-5 text-sm text-[var(--clay)]">{error}</p> : null}

      <section>
        <h2 className="text-2xl font-semibold">等你回应</h2>
        <div className="mt-4 grid gap-4">
          {incoming.data?.map((request) => (
            <article key={request.id} className="panel">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="eyebrow">连接请求</p>
                  <h3 className="mt-2 text-2xl font-semibold">{request.other_user.display_name}</h3>
                </div>
                <span className="chip">等待你的选择</span>
              </div>
              <div className="mt-5 rounded-2xl bg-[rgba(46,107,87,0.07)] p-4">
                <p className="text-sm font-semibold">对方想先了解</p>
                <p className="mt-2 leading-7">{request.topic_text}</p>
                {request.personal_message ? (
                  <p className="muted mt-3 text-sm leading-6">“{request.personal_message}”</p>
                ) : null}
              </div>
              <RequestContext request={request} />
              <div className="mt-6 flex flex-wrap gap-3">
                <button
                  className="button-primary"
                  onClick={() => accept.mutate(request.id)}
                  disabled={accept.isPending}
                >
                  愿意聊聊
                </button>
                <button
                  className="chip"
                  onClick={() => decline.mutate(request.id)}
                  disabled={decline.isPending}
                >
                  暂不联系
                </button>
              </div>
            </article>
          ))}
          {!incoming.isLoading && !incoming.data?.length ? (
            <p className="panel muted leading-7">暂时没有需要回应的连接请求。</p>
          ) : null}
        </div>
      </section>

      <section className="mt-10">
        <h2 className="text-2xl font-semibold">你发出的请求</h2>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          {outgoing.data?.map((request) => (
            <article key={request.id} className="panel">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="text-xl font-semibold">{request.other_user.display_name}</h3>
                  <p className="muted mt-2 text-sm leading-6">{request.topic_text}</p>
                </div>
                <span className="chip">等待回应</span>
              </div>
              <button className="chip mt-5" onClick={() => cancel.mutate(request.id)}>
                撤回请求
              </button>
            </article>
          ))}
          {!outgoing.isLoading && !outgoing.data?.length ? (
            <p className="panel muted leading-7">还没有发出的连接请求。</p>
          ) : null}
        </div>
      </section>
    </div>
  );
}

function RequestContext({ request }: { request: ConnectionRequest }) {
  const groups = [
    ["共同点", request.context_snapshot.common_signals],
    ["可能需要确认", request.context_snapshot.differences],
    ["仍然不知道", request.context_snapshot.unknowns],
  ] as const;
  return (
    <div className="mt-5 grid gap-3 md:grid-cols-3">
      {groups.map(([title, items]) =>
        items?.length ? (
          <div key={title} className="signal-card">
            <p className="text-sm font-semibold">{title}</p>
            <ul className="muted mt-2 space-y-2 text-xs leading-5">
              {items.slice(0, 2).map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        ) : null,
      )}
    </div>
  );
}
