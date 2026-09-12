"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { ApiError, apiFetch, postJson } from "@/lib/api";

type Match = { id: string; other_user: { id: string; display_name: string }; status: string };
type Outcome = {
  id: string;
  candidate_id: string;
  window_days: number;
  satisfaction: string;
  growth_alignment: string | null;
  boundary_respect: string | null;
  continued_contact: boolean;
  good_outcome: boolean;
};

export default function OutcomesPage() {
  const queryClient = useQueryClient();
  const [matchId, setMatchId] = useState("");
  const [windowDays, setWindowDays] = useState<7 | 14 | 30>(14);
  const [satisfaction, setSatisfaction] = useState("positive");
  const [growth, setGrowth] = useState("positive");
  const [boundary, setBoundary] = useState("positive");
  const [continued, setContinued] = useState(true);
  const [error, setError] = useState("");
  const matches = useQuery({ queryKey: ["matches"], queryFn: () => apiFetch<Match[]>("/matches") });
  const outcomes = useQuery({ queryKey: ["outcomes"], queryFn: () => apiFetch<Outcome[]>("/outcomes") });
  const selected = matches.data?.find((item) => item.id === matchId) ?? matches.data?.[0];

  const submit = useMutation({
    mutationFn: () =>
      postJson<Outcome>("/outcomes", {
        candidate_id: selected?.other_user.id,
        match_id: selected?.id,
        window_days: windowDays,
        satisfaction,
        growth_alignment: windowDays === 30 ? growth : null,
        boundary_respect: windowDays === 30 ? boundary : null,
        continued_contact: continued,
        safety_event: false,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["outcomes"] });
      setError("");
    },
    onError: (reason) => setError(reason instanceof ApiError ? reason.message : "反馈未提交成功。"),
  });

  return (
    <div className="mx-auto max-w-4xl pb-20">
      <p className="eyebrow">结果反馈</p>
      <h1 className="mt-3 text-3xl font-semibold sm:text-4xl">用真实相处感受校正关系线索</h1>
      <p className="muted mt-4 max-w-3xl leading-7">
        7、14、30 天反馈用于衡量安全、继续交流和边界尊重，不用于给某个人打分。
        你可以跳过，也可以撤回结果反馈授权。
      </p>

      {!matches.data?.length ? (
        <section className="panel mt-8"><p>开启一段交流后，这里会出现可反馈的关系。</p></section>
      ) : (
        <form
          className="panel mt-8 space-y-7"
          onSubmit={(event) => { event.preventDefault(); submit.mutate(); }}
        >
          <label className="block font-medium">
            选择关系
            <select className="field mt-2" value={selected?.id ?? ""} onChange={(event) => setMatchId(event.target.value)}>
              {matches.data.map((match) => (
                <option key={match.id} value={match.id}>{match.other_user.display_name}</option>
              ))}
            </select>
          </label>

          <fieldset>
            <legend className="font-medium">反馈时间点</legend>
            <div className="mt-3 flex gap-2">
              {[7, 14, 30].map((days) => (
                <button
                  type="button"
                  key={days}
                  className={`chip ${windowDays === days ? "border-[var(--moss)] bg-[rgba(46,107,87,0.08)]" : ""}`}
                  onClick={() => setWindowDays(days as 7 | 14 | 30)}
                >
                  第 {days} 天
                </button>
              ))}
            </div>
          </fieldset>

          <Choice name="satisfaction" value={satisfaction} onChange={setSatisfaction} label="目前整体感受" />
          {windowDays === 30 ? (
            <>
              <Choice name="growth" value={growth} onChange={setGrowth} label="成长方向与节奏" />
              <Choice name="boundary" value={boundary} onChange={setBoundary} label="时间、空间与边界" />
            </>
          ) : null}

          <label className="flex items-center gap-3">
            <input type="checkbox" checked={continued} onChange={(event) => setContinued(event.target.checked)} />
            <span>目前愿意继续保持联系</span>
          </label>
          {error ? <p className="text-sm text-[var(--clay)]">{error}</p> : null}
          <button className="button-primary" disabled={submit.isPending}>{submit.isPending ? "正在记录…" : "提交反馈"}</button>
        </form>
      )}

      {outcomes.data?.length ? (
        <section className="mt-10">
          <h2 className="text-2xl font-semibold">已经记录的反馈</h2>
          <div className="mt-5 grid gap-4 sm:grid-cols-2">
            {outcomes.data.map((item) => (
              <article key={item.id} className="signal-card">
                <p className="font-semibold">第 {item.window_days} 天</p>
                <p className="muted mt-2 text-sm">整体感受：{label(item.satisfaction)}</p>
                {item.window_days === 30 ? (
                  <>
                    <p className="muted mt-2 text-sm">成长同向：{label(item.growth_alignment)}</p>
                    <p className="muted mt-2 text-sm">边界尊重：{label(item.boundary_respect)}</p>
                  </>
                ) : null}
              </article>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}

function Choice({ name, value, onChange, label }: { name: string; value: string; onChange: (value: string) => void; label: string }) {
  return (
    <fieldset>
      <legend className="font-medium">{label}</legend>
      <div className="mt-3 flex flex-wrap gap-2">
        {[["positive", "积极"], ["neutral", "还可以"], ["negative", "不太好"]].map(([item, text]) => (
          <label key={item} className={`chip cursor-pointer ${value === item ? "border-[var(--moss)] bg-[rgba(46,107,87,0.08)]" : ""}`}>
            <input className="sr-only" type="radio" name={name} value={item} checked={value === item} onChange={() => onChange(item)} />
            {text}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

function label(value: string | null) {
  return { positive: "积极", neutral: "还可以", negative: "不太好" }[value ?? ""] ?? "未填写";
}