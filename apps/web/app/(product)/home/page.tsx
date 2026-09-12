"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useMemo, useState } from "react";

import { ApiError, apiFetch, postJson } from "@/lib/api";
import { CONSENT_SCOPES } from "@/lib/consent";

type Claim = {
  id: string;
  dimension: string;
  value: string | string[];
  evidence_ids: string[];
  user_confirmed: boolean;
  correction_state: string | null;
  expires_at: string;
};
type Option = { value: string; label: string };
type Question = { id: string; dimension: string; prompt: string; options: Option[] };
type Questionnaire = { questions: Question[] };
type Consent = { scope: string; revoked_at: string | null };
type CandidateLead = {
  recommendation_id: string;
  candidate_id: string;
  display_name: string;
  headline: string;
  common_signals: string[];
  differences: string[];
  unknowns: string[];
  how_to_continue: string[];
  evidence_ids: string[];
};
type RecommendationBundle = { generated_at: string; session_id: string; items: CandidateLead[] };

export default function HomePage() {
  const queryClient = useQueryClient();
  const [recs, setRecs] = useState<RecommendationBundle | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const claims = useQuery({ queryKey: ["claims"], queryFn: () => apiFetch<Claim[]>("/claims") });
  const consents = useQuery({ queryKey: ["consents"], queryFn: () => apiFetch<Consent[]>("/consents") });
  const questionnaire = useQuery({
    queryKey: ["questionnaire"],
    queryFn: () => apiFetch<Questionnaire>("/questionnaire"),
  });
  const activeScopes = new Set(consents.data?.filter((item) => !item.revoked_at).map((item) => item.scope) ?? []);
  const matchingAllowed = activeScopes.has("matching:v1");

  const labels = useMemo(() => {
    const map = new Map<string, string>();
    questionnaire.data?.questions.forEach((question) => {
      question.options.forEach((option) => map.set(option.value, option.label));
    });
    return map;
  }, [questionnaire.data]);

  const feedback = useMutation({
    mutationFn: ({ id, value }: { id: string; value: string }) =>
      postJson(`/claims/${id}/feedback`, { feedback: value }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["claims"] });
      setMessage("反馈已记录，后续解释会按你的修正更新。");
    },
  });

  const removeClaim = useMutation({
    mutationFn: (id: string) => apiFetch<void>(`/claims/${id}`, { method: "DELETE" }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["claims"] });
      setMessage("该线索已从匹配用途中移除。");
    },
  });

  const generate = useMutation({
    mutationFn: () =>
      apiFetch<RecommendationBundle>("/recommendations", {
        method: "POST",
        headers: { "X-Session-Id": crypto.randomUUID(), "Idempotency-Key": crypto.randomUUID() },
      }),
    onSuccess: (data) => {
      setRecs(data);
      setError("");
    },
    onError: (reason) => {
      setError(reason instanceof ApiError ? reason.message : "暂时无法生成关系线索。");
    },
  });

  if (!matchingAllowed) {
    return (
      <section className="panel mx-auto max-w-3xl">
        <p className="eyebrow">授权尚未完成</p>
        <h1 className="mt-3 text-3xl font-semibold">匹配用途当前处于关闭状态</h1>
        <p className="muted mt-4 leading-7">
          只有在“关系匹配”授权有效时，系统才会读取经过确认的关系信号。
        </p>
        <Link className="button-primary mt-7" href="/onboarding">
          继续授权与问卷
        </Link>
      </section>
    );
  }

  return (
    <div className="space-y-10 pb-20">
      <section className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="panel">
          <p className="eyebrow">当前关系信号</p>
          <h1 className="mt-3 text-3xl font-semibold sm:text-4xl">先确认你此刻的选择</h1>
          <p className="muted mt-4 max-w-2xl leading-7">
            这些不是对你的定义。你可以对每条线索选择“更像”“不太像”或“不确定”，也可以直接移除。
          </p>
          {message ? <p className="mt-5 rounded-2xl bg-[rgba(46,107,87,0.08)] p-3 text-sm">{message}</p> : null}
          <div className="mt-7 grid gap-4 md:grid-cols-2">
            {claims.data?.slice(0, 8).map((claim) => {
              const values = Array.isArray(claim.value) ? claim.value : [claim.value];
              const question = questionnaire.data?.questions.find((item) => item.dimension === claim.dimension);
              return (
                <article key={claim.id} className="signal-card">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <span className="text-xs font-semibold text-[var(--moss)]">目前更接近</span>
                      <p className="mt-2 font-medium leading-6">
                        {values.map((value) => labels.get(value) ?? value).join("、")}
                      </p>
                    </div>
                    <button
                      type="button"
                      className="text-xs underline underline-offset-4"
                      onClick={() => removeClaim.mutate(claim.id)}
                    >
                      删除
                    </button>
                  </div>
                  {question ? <p className="muted mt-3 text-xs leading-5">{question.prompt}</p> : null}
                  <div className="mt-4 flex flex-wrap gap-2">
                    {[
                      ["more_like_this", "更像"],
                      ["not_like_this", "不太像"],
                      ["unsure", "不确定"],
                    ].map(([value, text]) => (
                      <button
                        key={value}
                        type="button"
                        className={`chip text-xs ${claim.correction_state === value ? "border-[var(--moss)] text-[var(--moss)]" : ""}`}
                        onClick={() => feedback.mutate({ id: claim.id, value })}
                      >
                        {text}
                      </button>
                    ))}
                  </div>
                </article>
              );
            })}
          </div>
          {!claims.data?.length ? (
            <Link className="button-primary mt-7" href="/onboarding">
              完成场景取舍题
            </Link>
          ) : null}
        </div>

        <aside className="panel self-start lg:sticky lg:top-24">
          <p className="eyebrow">下一步</p>
          <h2 className="mt-3 text-2xl font-semibold">从可讨论的关系线索开始</h2>
          <p className="muted mt-4 leading-7">
            每次展示都会记录策略版本与曝光位置。排序只决定先看到谁，不会变成对人的评价。
          </p>
          <button
            className="button-primary mt-6 w-full"
            onClick={() => generate.mutate()}
            disabled={generate.isPending || !claims.data?.length}
          >
            {generate.isPending ? "正在整理共同点与未知项…" : "生成一组关系线索"}
          </button>
          {error ? <p className="mt-4 text-sm text-[var(--clay)]">{error}</p> : null}
          <div className="muted mt-5 space-y-3 text-xs leading-5">
            {CONSENT_SCOPES.map((item) => (
              <p key={item.scope}>
                {activeScopes.has(item.scope) ? "已授权" : "未授权"} · {item.title}
              </p>
            ))}
          </div>
        </aside>
      </section>

      {recs ? (
        <section aria-labelledby="recommendations-title">
          <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="eyebrow">继续了解</p>
              <h2 id="recommendations-title" className="mt-2 text-3xl font-semibold">
                共同点、差异与还不知道的事
              </h2>
            </div>
            <p className="muted max-w-md text-sm leading-6">
              以下顺序仅用于本次展示，不表示关系结论；部分位置会保留给新的可能。
            </p>
          </div>
          <div className="grid gap-5 lg:grid-cols-2">
            {recs.items.map((item) => (
              <article key={item.candidate_id} className="panel flex flex-col">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h3 className="text-2xl font-semibold">{item.display_name}</h3>
                    <p className="muted mt-2 leading-6">{item.headline}</p>
                  </div>
                  <span className="chip shrink-0">可继续了解</span>
                </div>
                <div className="mt-6 space-y-3">
                  <Explanation title="目前看到的共同点" items={item.common_signals} tone="signal-positive" />
                  <Explanation title="可能需要进一步确认的差异" items={item.differences} tone="signal-difference" />
                  <Explanation title="现在仍然不知道的事情" items={item.unknowns} tone="signal-unknown" />
                </div>
                <div className="mt-6 rounded-2xl bg-[rgba(46,107,87,0.07)] p-4">
                  <p className="text-sm font-semibold">可以怎样继续了解</p>
                  <ul className="muted mt-2 list-disc space-y-2 pl-5 text-sm leading-6">
                    {item.how_to_continue.map((text) => (
                      <li key={text}>{text}</li>
                    ))}
                  </ul>
                </div>
                <Link className="button-primary mt-6 self-start" href={`/recommendations/${item.candidate_id}`}>
                  先看具体线索
                </Link>
              </article>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}

function Explanation({ title, items, tone }: { title: string; items: string[]; tone: string }) {
  if (!items.length) return null;
  return (
    <div className={`signal-card ${tone}`}>
      <p className="text-sm font-semibold">{title}</p>
      <ul className="muted mt-2 space-y-2 text-sm leading-6">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}
