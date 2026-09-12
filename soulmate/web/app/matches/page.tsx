"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { apiFetch, describeError } from "../../lib/api";
import type { MatchOut, UserOut } from "../../lib/api/types";

export default function MatchesPage() {
  const [me, setMe] = useState<UserOut | null>(null);
  const [matches, setMatches] = useState<MatchOut[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setMe(await apiFetch<UserOut>("/auth/me"));
      setMatches(await apiFetch<MatchOut[]>("/matches"));
    } catch (err) {
      setMe(null);
      setError(describeError(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) {
    return (
      <main className="container">
        <div className="card">正在读取…</div>
      </main>
    );
  }

  if (!me) {
    return (
      <main className="container">
        <div className="card">
          <div className="h2">还没有登录</div>
          <div className="muted mt8">{error ?? "请先回到首页选择演示账号登录。"}</div>
          <div className="btnRow">
            <Link className="btn btnPrimary" href="/" style={{ textAlign: "center" }}>
              回到首页
            </Link>
          </div>
        </div>
      </main>
    );
  }

  const connected = matches.filter((m) => m.status === "connected");
  const pending = matches.filter((m) => m.status !== "connected");

  return (
    <main className="container">
      <div className="row">
        <div>
          <div className="h1">我的匹配</div>
          <div className="muted mt4" style={{ fontSize: 13 }}>
            只有互相邀请之后才会建立联系，之后才能聊天。
          </div>
        </div>
        <button className="navBtn" style={{ width: "auto" }} onClick={() => void load()}>
          刷新
        </button>
      </div>

      {error ? <div className="banner bannerError">{error}</div> : null}

      <div className="card">
        <div className="h2">已建立联系（{connected.length}）</div>
        {connected.length === 0 ? (
          <div className="muted mt8">还没有。被对方回应后，这里会出现可以聊天的人。</div>
        ) : (
          connected.map((m) => (
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

      <div style={{ height: 14 }} />

      <div className="card">
        <div className="h2">等待回应（{pending.length}）</div>
        {pending.length === 0 ? (
          <div className="muted mt8">没有待回应的邀请。</div>
        ) : (
          pending.map((m) => (
            <div key={m.match_id} className="claimRow">
              <div>对方 id：{m.candidate_id}</div>
              <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
                已经发出邀请，等 TA 回应。状态：{m.status}
              </div>
            </div>
          ))
        )}
      </div>
    </main>
  );
}
