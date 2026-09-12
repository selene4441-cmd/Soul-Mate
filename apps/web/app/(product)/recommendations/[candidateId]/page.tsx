"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";

import { ApiError, apiFetch } from "@/lib/api";

type Lead = {
  candidate_id: string;
  display_name: string;
  headline: string;
  common_signals: string[];
  differences: string[];
  unknowns: string[];
  how_to_continue: string[];
};

export default function CandidatePage() {
  const params = useParams<{ candidateId: string }>();
  const router = useRouter();
  const [error, setError] = useState("");
  const lead = useQuery({
    queryKey: ["candidate", params.candidateId],
    queryFn: () => apiFetch<Lead>(`/recommendations/${params.candidateId}`),
  });
  const invite = useMutation({
    mutationFn: () =>
      apiFetch("/invitations", {
        method: "POST",
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: JSON.stringify({ candidate_id: params.candidateId, message: "想从具体相处情境开始了解。" }),
      }),
    onSuccess: () => router.push("/messages"),
    onError: (reason) => setError(reason instanceof ApiError ? reason.message : "邀请未发送成功。"),
  });

  if (lead.isLoading) return <p className="muted">正在读取关系线索…</p>;
  if (lead.error || !lead.data) {
    return <section className="panel"><h1 className="text-2xl font-semibold">这条线索当前不可查看</h1></section>;
  }

  return (
    <div className="mx-auto max-w-4xl pb-20">
      <Link href="/home" className="muted text-sm underline underline-offset-4">返回关系线索</Link>
      <header className="panel mt-5">
        <p className="eyebrow">继续了解</p>
        <h1 className="mt-3 text-4xl font-semibold">{lead.data.display_name}</h1>
        <p className="muted mt-3 text-lg leading-7">{lead.data.headline}</p>
        <p className="muted mt-5 text-sm leading-6">解释来自双方主动填写的内容，不代表已经了解真实相处感受。</p>
      </header>
      <div className="mt-6 grid gap-5 md:grid-cols-2">
        <Block title="目前看到的共同点" items={lead.data.common_signals} tone="signal-positive" />
        <Block title="可能需要进一步确认的差异" items={lead.data.differences} tone="signal-difference" />
        <Block title="现在仍然不知道的事情" items={lead.data.unknowns} tone="signal-unknown" />
        <Block title="可以怎样继续了解" items={lead.data.how_to_continue} tone="" />
      </div>
      <section className="panel mt-6">
        <h2 className="text-2xl font-semibold">在双方同意后开启交流</h2>
        <p className="muted mt-3 leading-7">邀请表示愿意进一步了解；系统会继续检查双方授权与安全状态。</p>
        {error ? <p className="mt-4 text-sm text-[var(--clay)]">{error}</p> : null}
        <button className="button-primary mt-6" onClick={() => invite.mutate()} disabled={invite.isPending}>
          {invite.isPending ? "正在确认双方状态…" : "发送了解邀请"}
        </button>
      </section>
    </div>
  );
}

function Block({ title, items, tone }: { title: string; items: string[]; tone: string }) {
  return (
    <section className={`signal-card ${tone}`}>
      <h2 className="font-semibold">{title}</h2>
      <ul className="muted mt-3 space-y-3 text-sm leading-6">
        {items.map((text) => <li key={text}>{text}</li>)}
      </ul>
    </section>
  );
}