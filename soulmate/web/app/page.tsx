"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { apiFetch, describeError, postJson } from "../lib/api";
import type {
  ClaimOut,
  ConsentOut,
  MatchOut,
  QuestionnaireOut,
  RecommendationItemOut,
  SpaceStateOut,
  UserOut
} from "../lib/api/types";

/** 演示账号：一键切换，正好覆盖四种 space/state */
const DEMO_ACCOUNTS = [
  { email: "demo1@example.com", name: "林屿", hint: "推荐列表（MATCHING）" },
  { email: "demo2@example.com", name: "苏晚", hint: "聊天（CHAT）" },
  { email: "demo3@example.com", name: "周聿", hint: "Your Story（SELF_PROFILE_READY）" },
  { email: "demo4@example.com", name: "何枝", hint: "问卷引导（EXPLORING）" }
];
const DEMO_PASSWORD = "password123";

type Banner = { kind: "error" | "info"; text: string } | null;

export default function HomePage() {
  const [ready, setReady] = useState(false);
  const [me, setMe] = useState<UserOut | null>(null);
  const [space, setSpace] = useState<SpaceStateOut | null>(null);
  const [questionnaire, setQuestionnaire] = useState<QuestionnaireOut | null>(null);
  const [consents, setConsents] = useState<ConsentOut[]>([]);
  const [claims, setClaims] = useState<ClaimOut[]>([]);
  const [items, setItems] = useState<RecommendationItemOut[]>([]);
  const [matches, setMatches] = useState<MatchOut[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [inviteText, setInviteText] = useState("想从一个具体场景开始了解。");
  const [banner, setBanner] = useState<Banner>(null);
  const [busy, setBusy] = useState<string | null>(null);

  /** 把 Claim 的 value（如 stay_home）翻成问卷里的中文选项 */
  const labels = useMemo(() => {
    const map = new Map<string, Map<string, string>>();
    for (const q of questionnaire?.questions ?? []) {
      const opts = new Map<string, string>();
      for (const o of q.options) opts.set(o.value, o.label);
      map.set(q.dimension, opts);
    }
    return map;
  }, [questionnaire]);

  const labelOf = useCallback(
    (dimension: string, value: string) => labels.get(dimension)?.get(value) ?? value,
    [labels]
  );

  const promptOf = useCallback(
    (dimension: string) => questionnaire?.questions.find((q) => q.dimension === dimension)?.prompt ?? dimension,
    [questionnaire]
  );

  const hasMatchingConsent = consents.some((c) => c.scope === "matching:v1");
  const hasConversationConsent = consents.some((c) => c.scope === "conversation:v1");

  const load = useCallback(async () => {
    setBanner(null);
    try {
      const user = await apiFetch<UserOut>("/auth/me");
      setMe(user);
    } catch {
      setMe(null);
      setSpace(null);
      return;
    }

    try {
      const state = await apiFetch<SpaceStateOut>("/space/state");
      setSpace(state);

      const [qs, cs] = await Promise.all([
        apiFetch<QuestionnaireOut>("/questionnaire"),
        apiFetch<ConsentOut[]>("/consents").catch(() => [])
      ]);
      setQuestionnaire(qs);
      setConsents(cs);

      if (state.state === "SELF_PROFILE_READY" || state.state === "CHAT") {
        setClaims(await apiFetch<ClaimOut[]>("/claims").catch(() => []));
      }
      if (state.state === "MATCHING") {
        const recos = await postJson<{ items: RecommendationItemOut[] }>("/recommendations");
        setItems(recos.items ?? []);
      }
      if (state.state === "CHAT") {
        setMatches(await apiFetch<MatchOut[]>("/matches").catch(() => []));
      }
    } catch (error) {
      setBanner({ kind: "error", text: describeError(error) });
    }
  }, []);

  useEffect(() => {
    void (async () => {
      // 深链接：/?login=demo1@example.com 直接用内置演示账号进入（非演示邮箱会被忽略）
      const requested =
        typeof window !== "undefined"
          ? new URLSearchParams(window.location.search).get("login")
          : null;
      const account = requested ? DEMO_ACCOUNTS.find((a) => a.email === requested) : undefined;
      if (account) {
        try {
          await postJson("/auth/login", { email: account.email, password: DEMO_PASSWORD });
        } catch {
          // 登录失败就让用户手动选账号，不阻塞页面
        }
      }
      await load();
      setReady(true);
    })();
  }, [load]);

  async function run(key: string, fn: () => Promise<void>) {
    setBusy(key);
    setBanner(null);
    try {
      await fn();
    } catch (error) {
      setBanner({ kind: "error", text: describeError(error) });
    } finally {
      setBusy(null);
    }
  }

  const login = (email: string, password: string) =>
    run("login", async () => {
      await postJson("/auth/login", { email, password });
      await load();
    });

  const register = (form: RegisterForm) =>
    run("register", async () => {
      await postJson("/auth/register", form);
      await load();
    });

  const grantConsent = (scope: "matching:v1" | "conversation:v1", purpose: string) =>
    run(`consent:${scope}`, async () => {
      await postJson("/consents", { scope, purpose });
      await load();
    });

  const submitQuestionnaire = () =>
    run("questionnaire", async () => {
      if (!questionnaire) return;
      await postJson("/questionnaire/submissions", { version: questionnaire.version, answers });
      setAnswers({});
      await load();
    });

  const generateRecommendations = () =>
    run("recos", async () => {
      const recos = await postJson<{ items: RecommendationItemOut[] }>("/recommendations");
      setItems(recos.items ?? []);
      await load();
    });

  const invite = (candidateId: string) =>
    run(`invite:${candidateId}`, async () => {
      const result = await postJson<{ match_id: string; status: string }>("/invitations", {
        candidate_id: candidateId,
        message: inviteText.trim() || "想从一个具体场景开始了解。"
      });
      setBanner({
        kind: "info",
        text:
          result.status === "connected"
            ? "对方也邀请了你，已经建立联系，可以去聊天了。"
            : "邀请已发出，等对方回应后会建立联系。"
      });
      await load();
    });

  if (!ready) {
    return (
      <main className="container">
        <div className="card">正在读取状态…</div>
      </main>
    );
  }

  if (!me) {
    return (
      <main className="container">
        <BannerView banner={banner} />
        <div className="card">
          <div className="h1">先登录，再开始</div>
          <div className="muted mt8">
            演示账号密码统一是 <code>{DEMO_PASSWORD}</code>。四个账号分别停在四种界面状态，点一下就能看到。
          </div>
          <div className="grid2 mt16">
            {DEMO_ACCOUNTS.map((acct) => (
              <button
                key={acct.email}
                className="btn"
                disabled={busy !== null}
                onClick={() => void login(acct.email, DEMO_PASSWORD)}
              >
                <div style={{ fontWeight: 700 }}>{acct.name}</div>
                <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
                  {acct.hint}
                </div>
              </button>
            ))}
          </div>
        </div>

        <div style={{ height: 14 }} />
        <AuthForms busy={busy !== null} onLogin={login} onRegister={register} />
      </main>
    );
  }

  return (
    <main className="container">
      <div className="row">
        <div>
          <div className="h1">你好，{me.display_name}</div>
          <div className="muted mt4" style={{ fontSize: 13 }}>
            当前状态：<span className="badge">{space?.state ?? "读取中"}</span>
            {space?.can_match ? <span className="muted"> · 已满足开始匹配的条件</span> : null}
          </div>
        </div>
        <button className="navBtn" style={{ width: "auto" }} disabled={busy !== null} onClick={() => void load()}>
          刷新状态
        </button>
      </div>

      <BannerView banner={banner} />

      {space?.state === "EXPLORING" ? (
        <>
          {!hasMatchingConsent ? (
            <div className="card">
              <div className="h2">先说明用途，再请你授权</div>
              <div className="muted mt8">
                我们只会用你的回答来判断「哪些人和你更接近」。不会展示任何匹配分数或人格标签，
                你随时可以在这里撤销授权。
              </div>
              <div className="btnRow">
                <button
                  className="btn btnPrimary"
                  disabled={busy !== null}
                  onClick={() => void grantConsent("matching:v1", "用于关系匹配")}
                >
                  同意用于匹配
                </button>
              </div>
            </div>
          ) : (
            <QuestionnaireCard
              questionnaire={questionnaire}
              answers={answers}
              busy={busy !== null}
              onPick={(dimension, value) => setAnswers((prev) => ({ ...prev, [dimension]: value }))}
              onSubmit={() => void submitQuestionnaire()}
            />
          )}
        </>
      ) : null}

      {space?.state === "SELF_PROFILE_READY" ? (
        <>
          <div className="card">
            <div className="h2">Your Story</div>
            <div className="muted mt8">这是你告诉我们的内容，不是我们对你的评价。</div>
            <div className="mt16">
              {claims.length === 0 ? (
                <div className="muted">还没有可以展示的内容。</div>
              ) : (
                claims.map((claim) => (
                  <div key={claim.id} className="claimRow">
                    <div className="muted" style={{ fontSize: 12 }}>
                      {promptOf(claim.dimension)}
                    </div>
                    <div style={{ marginTop: 4 }}>{labelOf(claim.dimension, claim.value)}</div>
                  </div>
                ))
              )}
            </div>
          </div>

          <div style={{ height: 14 }} />
          <div className="card">
            <div className="h2">看看可能的人</div>
            <div className="muted mt8">
              我们会基于你的回答找出「共同点、差异、以及还不确定的部分」，而不是给你一个分数。
            </div>
            <div className="btnRow">
              <button
                className="btn btnPrimary"
                disabled={busy !== null}
                onClick={() => void generateRecommendations()}
              >
                {busy === "recos" ? "正在整理…" : "看看可能的人"}
              </button>
            </div>
          </div>
        </>
      ) : null}

      {space?.state === "MATCHING" ? (
        <>
          <div className="row" style={{ marginBottom: 10 }}>
            <div className="h2">可能接近的人</div>
            <button className="navBtn" style={{ width: "auto" }} disabled={busy !== null} onClick={() => void generateRecommendations()}>
              重新整理
            </button>
          </div>
          {items.length === 0 ? (
            <div className="card muted">暂时没有可以展示的人。等更多人完成回答后再来看看。</div>
          ) : (
            items.map((item) => (
              <div key={item.recommendation_id} className="card mb14">
                <div className="h2">{item.display_name}</div>
                <div className="mt8">{item.headline}</div>

                <Section title="共同点" lines={item.common_signals} fallback="现在还没有明确的共同点。" />
                <Section title="差异" lines={item.differences} fallback="现在还没有明显的差异。" />
                <Section title="还不确定" lines={item.unknowns} fallback="该了解的都已经了解了。" />

                {item.how_to_continue.length > 0 ? (
                  <div className="mt12">
                    <div className="sectionTitle">可以这样开始</div>
                    <ul className="list">
                      {item.how_to_continue.map((line) => (
                        <li key={line}>{line}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}

                {!hasConversationConsent ? (
                  <div className="btnRow">
                    <button
                      className="btn"
                      disabled={busy !== null}
                      onClick={() => void grantConsent("conversation:v1", "用于建立联系后聊天")}
                    >
                      授权后才能发出邀请
                    </button>
                  </div>
                ) : (
                  <>
                    <div className="mt12">
                      <div className="sectionTitle">想对 TA 说</div>
                      <textarea
                        className="textarea"
                        rows={2}
                        value={inviteText}
                        onChange={(e) => setInviteText(e.target.value)}
                      />
                    </div>
                    <div className="btnRow">
                      <button
                        className="btn btnPrimary"
                        disabled={busy !== null}
                        onClick={() => void invite(item.candidate_id)}
                      >
                        {busy === `invite:${item.candidate_id}` ? "发送中…" : "发出邀请"}
                      </button>
                    </div>
                  </>
                )}
              </div>
            ))
          )}
        </>
      ) : null}

      {space?.state === "CHAT" ? (
        <>
          <div className="card">
            <div className="h2">已经建立联系</div>
            <div className="muted mt8">你们互相邀请之后就可以聊天了。下面是从后端读到的真实会话。</div>
            <div className="mt16">
              {matches.filter((m) => m.status === "connected").length === 0 ? (
                <div className="muted">还没有已建立的会话。</div>
              ) : (
                matches
                  .filter((m) => m.status === "connected")
                  .map((m) => (
                    <div key={m.match_id} className="row" style={{ padding: "10px 0" }}>
                      <div>
                        <div>对方 id：{m.candidate_id}</div>
                        <div className="muted" style={{ fontSize: 12 }}>
                          {m.connected_at ? `建立于 ${m.connected_at}` : ""}
                        </div>
                      </div>
                      <Link className="navBtn" style={{ width: "auto" }} href={`/chat/${m.match_id}`}>
                        进入聊天
                      </Link>
                    </div>
                  ))
              )}
            </div>
          </div>

          {claims.length > 0 ? (
            <>
              <div style={{ height: 14 }} />
              <div className="card">
                <div className="h2">How I See You</div>
                <div className="muted mt8">基于你自己的回答整理，随时可以改。</div>
                <div className="mt12">
                  {claims.map((claim) => (
                    <div key={claim.id} className="claimRow">
                      <div className="muted" style={{ fontSize: 12 }}>
                        {promptOf(claim.dimension)}
                      </div>
                      <div style={{ marginTop: 4 }}>{labelOf(claim.dimension, claim.value)}</div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          ) : null}
        </>
      ) : null}
    </main>
  );
}

/* --------------------------------------------------------------- 子组件 */

function BannerView({ banner }: { banner: Banner }) {
  if (!banner) return null;
  return (
    <div className={banner.kind === "error" ? "banner bannerError" : "banner bannerInfo"}>
      {banner.text}
    </div>
  );
}

function Section({ title, lines, fallback }: { title: string; lines: string[]; fallback: string }) {
  return (
    <div className="mt12">
      <div className="sectionTitle">{title}</div>
      {lines.length === 0 ? (
        <div className="muted" style={{ fontSize: 13 }}>
          {fallback}
        </div>
      ) : (
        <ul className="list">
          {lines.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

function QuestionnaireCard({
  questionnaire,
  answers,
  busy,
  onPick,
  onSubmit
}: {
  questionnaire: QuestionnaireOut | null;
  answers: Record<string, string>;
  busy: boolean;
  onPick: (dimension: string, value: string) => void;
  onSubmit: () => void;
}) {
  if (!questionnaire) return <div className="card muted">正在读取问卷…</div>;

  const requiredDimensions = questionnaire.questions.filter((q) => q.required).map((q) => q.dimension);
  const answered = requiredDimensions.filter((d) => answers[d]);
  const done = answered.length === requiredDimensions.length;

  return (
    <div className="card">
      <div className="h2">先回答几个问题</div>
      <div className="muted mt8">
        约 {questionnaire.estimated_minutes} 分钟。题目没有对错，选「更接近现在的你」就好。已答 {answered.length}/
        {requiredDimensions.length}。
      </div>

      {questionnaire.questions.map((q) => (
        <div key={q.id} className="mt16">
          <div style={{ fontWeight: 600 }}>{q.prompt}</div>
          <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
            {q.section} · {q.help_text}
          </div>
          <div className="grid2 mt10">
            {q.options.map((opt) => (
              <button
                key={opt.value}
                className={answers[q.dimension] === opt.value ? "btn btnPrimary" : "btn"}
                disabled={busy}
                onClick={() => onPick(q.dimension, opt.value)}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      ))}

      <div className="btnRow">
        <button className="btn btnPrimary" disabled={busy || !done} onClick={onSubmit}>
          {busy ? "提交中…" : done ? "提交回答" : "还有题目没答"}
        </button>
      </div>
    </div>
  );
}

type RegisterForm = {
  display_name: string;
  email: string;
  password: string;
  region: string;
  birth_year?: number;
};

function AuthForms({
  busy,
  onLogin,
  onRegister
}: {
  busy: boolean;
  onLogin: (email: string, password: string) => void;
  onRegister: (form: RegisterForm) => void;
}) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [region, setRegion] = useState("上海");

  return (
    <div className="card">
      <div className="row">
        <div className="h2">{mode === "login" ? "用已有账号登录" : "创建新账号"}</div>
        <button
          className="navBtn"
          style={{ width: "auto" }}
          onClick={() => setMode(mode === "login" ? "register" : "login")}
        >
          {mode === "login" ? "改成注册" : "改成登录"}
        </button>
      </div>

      {mode === "register" ? (
        <div className="mt12">
          <input className="input full" placeholder="昵称" value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
        </div>
      ) : null}

      <div className="mt12">
        <input className="input full" placeholder="邮箱" value={email} onChange={(e) => setEmail(e.target.value)} />
      </div>
      <div className="mt10">
        <input
          className="input full"
          placeholder="密码（至少 8 位）"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </div>
      {mode === "register" ? (
        <div className="mt10">
          <input className="input full" placeholder="所在城市" value={region} onChange={(e) => setRegion(e.target.value)} />
        </div>
      ) : null}

      <div className="btnRow">
        {mode === "login" ? (
          <button className="btn btnPrimary" disabled={busy || !email || !password} onClick={() => onLogin(email, password)}>
            登录
          </button>
        ) : (
          <button
            className="btn btnPrimary"
            disabled={busy || !email || !password || !displayName}
            onClick={() =>
              onRegister({ display_name: displayName, email, password, region, birth_year: undefined })
            }
          >
            注册并进入
          </button>
        )}
      </div>
    </div>
  );
}
