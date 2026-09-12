"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ApiError, apiFetch } from "@/lib/api";

type Lead = {
  candidate_id: string;
  display_name: string;
  headline: string;
  common_signals: string[];
  differences: string[];
  unknowns: string[];
  how_to_continue: string[];
  recommendation_id: string;
};

type CueOption = {
  id: string;
  cue_type: "common" | "difference" | "unknown" | "boundary" | "custom";
  text: string;
};

export default function CandidatePage() {
  const params = useParams<{ candidateId: string }>();
  const router = useRouter();
  const [error, setError] = useState("");
  const [selectedCue, setSelectedCue] = useState<CueOption | null>(null);
  const [customTopic, setCustomTopic] = useState("");
  const [personalMessage, setPersonalMessage] = useState("我想从这个问题开始了解。");

  const lead = useQuery({
    queryKey: ["candidate", params.candidateId],
    queryFn: () => apiFetch<Lead>(`/recommendations/${params.candidateId}`),
  });
  const cues = useQuery({
    queryKey: ["candidate-cues", params.candidateId],
    queryFn: () => apiFetch<CueOption[]>(`/recommendations/${params.candidateId}/cues`),
  });

  useEffect(() => {
    if (!selectedCue && cues.data?.length) setSelectedCue(cues.data[0]);
  }, [cues.data, selectedCue]);

  const invite = useMutation({
    mutationFn: () => {
      const topic = customTopic.trim() || selectedCue?.text || "";
      return apiFetch("/connection-requests", {
        method: "POST",
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: JSON.stringify({
          candidate_id: params.candidateId,
          recommendation_id: lead.data?.recommendation_id,
          cue_type: customTopic.trim() ? "custom" : selectedCue?.cue_type ?? "unknown",
          topic_text: topic,
          personal_message: personalMessage.trim() || null,
        }),
      });
    },
    onSuccess: () => router.push("/requests"),
    onError: (reason) =>
      setError(reason instanceof ApiError ? reason.message : "连接请求未发送成功。"),
  });

  if (lead.isLoading) return <p className="muted">正在读取关系线索…</p>;
  if (lead.error || !lead.data) {
    return (
      <section className="panel">
        <h1 className="text-2xl font-semibold">这条线索当前不可查看</h1>
      </section>
    );
  }

  const canSend = Boolean((selectedCue?.text || customTopic.trim()) && !invite.isPending);

  return (
    <div className="mx-auto max-w-4xl pb-20">
      <Link href="/home" className="muted text-sm underline underline-offset-4">
        返回关系线索
      </Link>
      <header className="panel mt-5">
        <p className="eyebrow">继续了解</p>
        <h1 className="mt-3 text-4xl font-semibold">{lead.data.display_name}</h1>
        <p className="muted mt-3 text-lg leading-7">{lead.data.headline}</p>
        <p className="muted mt-5 text-sm leading-6">
          解释来自双方主动填写的内容，不代表已经了解真实相处感受。
        </p>
      </header>

      <div className="mt-6 grid gap-5 md:grid-cols-2">
        <Block title="目前看到的共同点" items={lead.data.common_signals} tone="signal-positive" />
        <Block
          title="可能需要进一步确认的差异"
          items={lead.data.differences}
          tone="signal-difference"
        />
        <Block title="现在仍然不知道的事情" items={lead.data.unknowns} tone="signal-unknown" />
        <Block title="可以怎样继续了解" items={lead.data.how_to_continue} tone="" />
      </div>

      <section className="panel mt-6">
        <p className="eyebrow">从具体问题开始</p>
        <h2 className="mt-3 text-2xl font-semibold">你想先确认哪一个具体情境？</h2>
        <p className="muted mt-3 leading-7">
          对方会先看到这个议题和你的个人说明，选择愿意聊聊后才会开启会话。
        </p>
        <div className="mt-5 grid gap-3">
          {cues.data?.map((cue) => (
            <button
              key={cue.id}
              type="button"
              onClick={() => {
                setSelectedCue(cue);
                setCustomTopic("");
              }}
              className={`rounded-2xl border p-4 text-left leading-6 ${
                selectedCue?.id === cue.id && !customTopic.trim()
                  ? "border-[var(--moss)] bg-[rgba(46,107,87,0.08)]"
                  : "border-[var(--line)] bg-white/60"
              }`}
            >
              {cue.text}
            </button>
          ))}
        </div>
        <label className="mt-5 block text-sm font-medium">
          也可以写下你自己的议题
          <textarea
            className="field mt-2 min-h-20 resize-none"
            value={customTopic}
            onChange={(event) => setCustomTopic(event.target.value)}
            maxLength={300}
            placeholder="例如：忙碌的一周里，什么方式最能让你感到被惦记？"
          />
        </label>
        <label className="mt-5 block text-sm font-medium">
          想让对方知道的一句说明
          <textarea
            className="field mt-2 min-h-20 resize-none"
            value={personalMessage}
            onChange={(event) => setPersonalMessage(event.target.value)}
            maxLength={300}
          />
        </label>
        {error ? <p className="mt-4 text-sm text-[var(--clay)]">{error}</p> : null}
        <button className="button-primary mt-6" onClick={() => invite.mutate()} disabled={!canSend}>
          {invite.isPending ? "正在发送连接请求…" : "发送了解邀请"}
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
        {items.map((text) => (
          <li key={text}>{text}</li>
        ))}
      </ul>
    </section>
  );
}
