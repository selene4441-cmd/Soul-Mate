"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { ApiError, apiFetch, postJson } from "@/lib/api";
import { CONSENT_SCOPES } from "@/lib/consent";

type Consent = { scope: string; revoked_at: string | null };
type Option = { value: string; label: string };
type Question = {
  id: string;
  section: string;
  dimension: string;
  prompt: string;
  help_text: string;
  kind: "single" | "multi";
  required: boolean;
  options: Option[];
};
type Questionnaire = { version: string; estimated_minutes: number; questions: Question[] };

export default function OnboardingPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [step, setStep] = useState<"consent" | "questions">("consent");
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string | string[]>>({});
  const [error, setError] = useState("");

  const consents = useQuery({
    queryKey: ["consents"],
    queryFn: () => apiFetch<Consent[]>("/consents"),
  });
  const activeScopes = useMemo(
    () => new Set(consents.data?.filter((item) => !item.revoked_at).map((item) => item.scope) ?? []),
    [consents.data],
  );
  const allGranted = CONSENT_SCOPES.every((item) => activeScopes.has(item.scope));

  const questionnaire = useQuery({
    queryKey: ["questionnaire"],
    queryFn: () => apiFetch<Questionnaire>("/questionnaire"),
    enabled: step === "questions" || allGranted,
  });

  const grantConsents = useMutation({
    mutationFn: async () => {
      for (const item of CONSENT_SCOPES) {
        await postJson<Consent>("/consents", { scope: item.scope, purpose: item.purpose });
      }
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["consents"] });
      setError("");
      setStep("questions");
    },
    onError: (reason) => {
      setError(reason instanceof ApiError ? reason.message : "授权记录未完成，请稍后重试。");
    },
  });

  const questions = questionnaire.data?.questions ?? [];
  const current = questions[index];
  const selected = current ? answers[current.id] : undefined;

  function choose(value: string) {
    if (!current) return;
    setError("");
    if (current.kind === "single") {
      setAnswers((previous) => ({ ...previous, [current.id]: value }));
      return;
    }
    const existing = Array.isArray(selected) ? selected : [];
    const next = existing.includes(value)
      ? existing.filter((item) => item !== value)
      : [...existing, value];
    setAnswers((previous) => ({ ...previous, [current.id]: next }));
  }

  const submit = useMutation({
    mutationFn: () =>
      postJson("/questionnaire/submissions", {
        version: questionnaire.data?.version,
        answers,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["claims"] });
      router.push("/home");
    },
    onError: (reason) => {
      setError(reason instanceof ApiError ? reason.message : "问卷未提交成功，请稍后重试。");
    },
  });

  function next() {
    if (!current) return;
    const hasValue = Array.isArray(selected) ? selected.length > 0 : Boolean(selected);
    if (current.required && !hasValue) {
      setError("先选择目前更接近你的情况，再继续。");
      return;
    }
    setError("");
    if (index === questions.length - 1) {
      submit.mutate();
      return;
    }
    setIndex((value) => value + 1);
  }

  if (step === "consent" && !allGranted) {
    return (
      <div className="mx-auto max-w-3xl">
        <p className="eyebrow">第 1 步 · 授权</p>
        <h1 className="mt-3 text-3xl font-semibold sm:text-4xl">先决定哪些数据用于什么目的</h1>
        <p className="muted mt-4 max-w-2xl leading-7">
          默认状态下不会进入匹配链路。你可以逐项授权，也可以稍后单独撤回；撤回后相关数据会停止用于对应用途。
        </p>
        <div className="mt-8 space-y-4">
          {CONSENT_SCOPES.map((item) => (
            <article key={item.scope} className="panel flex gap-4">
              <span
                aria-hidden
                className={`mt-1 grid h-7 w-7 shrink-0 place-items-center rounded-full border ${
                  activeScopes.has(item.scope)
                    ? "border-[var(--moss)] bg-[var(--moss)] text-white"
                    : "border-[var(--line)] bg-white"
                }`}
              >
                {activeScopes.has(item.scope) ? "✓" : ""}
              </span>
              <div>
                <h2 className="text-lg font-semibold">{item.title}</h2>
                <p className="muted mt-2 text-sm leading-6">{item.purpose}</p>
                <span className="mt-3 inline-block text-xs font-semibold text-[var(--moss)]">
                  版本 2026-09-12
                </span>
              </div>
            </article>
          ))}
        </div>
        <button
          className="button-primary mt-7 w-full sm:w-auto"
          onClick={() => grantConsents.mutate()}
          disabled={grantConsents.isPending || allGranted}
        >
          {allGranted ? "授权已记录" : grantConsents.isPending ? "正在记录…" : "同意以上范围并开始问卷"}
        </button>
        <p className="muted mt-4 text-xs leading-5">
          不授权“关系匹配”将无法生成推荐；不授权“双向交流”或“结果反馈”只会关闭对应功能。
        </p>
        {error ? <p className="mt-4 text-sm text-[var(--clay)]">{error}</p> : null}
      </div>
    );
  }

  if (questionnaire.isLoading || !current) {
    return <p className="muted">正在准备场景问题…</p>;
  }

  const progress = Math.round(((index + 1) / questions.length) * 100);

  return (
    <div className="mx-auto max-w-3xl">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="eyebrow">第 2 步 · 场景取舍</p>
          <p className="muted mt-2 text-sm">
            第 {index + 1} / {questions.length} 题 · 约 {questionnaire.data?.estimated_minutes} 分钟
          </p>
        </div>
        <button type="button" className="text-sm underline underline-offset-4" onClick={() => router.push("/home")}>
          暂时离开
        </button>
      </div>
      <div className="mt-5 h-2 overflow-hidden rounded-full bg-[#e4e4da]" aria-label={`问卷进度 ${progress}%`}>
        <div className="h-full rounded-full bg-[var(--moss)] transition-all" style={{ width: `${progress}%` }} />
      </div>

      <section className="panel mt-8" aria-labelledby="question-title">
        <span className="chip">{current.section}</span>
        <h1 id="question-title" className="mt-5 text-2xl font-semibold leading-9 sm:text-3xl">
          {current.prompt}
        </h1>
        <p className="muted mt-3 text-sm leading-6">{current.help_text}</p>
        <div className="mt-7 space-y-3">
          {current.options.map((option) => {
            const isSelected = Array.isArray(selected) ? selected.includes(option.value) : selected === option.value;
            return (
              <button
                type="button"
                key={option.value}
                onClick={() => choose(option.value)}
                className={`w-full rounded-2xl border px-4 py-4 text-left transition ${
                  isSelected
                    ? "border-[var(--moss)] bg-[rgba(46,107,87,0.08)]"
                    : "border-[var(--line)] bg-white hover:border-[var(--moss)]"
                }`}
                aria-pressed={isSelected}
              >
                <span className="flex items-center gap-3">
                  <span
                    className={`grid h-6 w-6 place-items-center rounded-full border ${
                      isSelected ? "border-[var(--moss)] bg-[var(--moss)] text-white" : "border-[var(--line)]"
                    }`}
                  >
                    {isSelected ? "✓" : ""}
                  </span>
                  <span>{option.label}</span>
                </span>
              </button>
            );
          })}
        </div>
        {error ? <p className="mt-4 text-sm text-[var(--clay)]">{error}</p> : null}
        <div className="mt-7 flex justify-between gap-3">
          <button
            type="button"
            className="button-secondary"
            onClick={() => setIndex((value) => Math.max(0, value - 1))}
            disabled={index === 0}
          >
            上一题
          </button>
          <button type="button" className="button-primary" onClick={next} disabled={submit.isPending}>
            {index === questions.length - 1
              ? submit.isPending
                ? "正在整理线索…"
                : "完成并查看线索"
              : "下一题"}
          </button>
        </div>
      </section>
    </div>
  );
}
