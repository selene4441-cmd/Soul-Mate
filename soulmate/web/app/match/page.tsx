"use client";

import { useEffect } from "react";
import { logClick } from "../../lib/events";
import { useUserId } from "../../lib/user";

export default function MatchPage() {
  const [userId] = useUserId();

  useEffect(() => {
    void logClick({ userId, eventType: "browse", targetId: "page:match", durationMs: 0 });
  }, [userId]);

  return (
    <main className="container">
      <div className="row">
        <div>
          <div style={{ fontSize: 18, fontWeight: 700 }}>匹配结果</div>
          <div className="muted" style={{ marginTop: 6, fontSize: 13 }}>
            当前页面仅展示占位（后续可接入后端匹配 API）。
          </div>
        </div>
        <button
          className="navBtn"
          onClick={() =>
            void logClick({
              userId,
              eventType: "browse",
              targetId: "match:refresh",
              durationMs: 0
            })
          }
        >
          刷新
        </button>
      </div>

      <div style={{ height: 14 }} />
      <div className="card">
        <div className="muted" style={{ fontSize: 12 }}>
          user_id: {userId}
        </div>
        <div style={{ fontSize: 20, lineHeight: 1.4, marginTop: 10 }}>
          你的匹配结果将出现在这里。
        </div>
        <div className="muted" style={{ marginTop: 10, fontSize: 13 }}>
          你可以先在“卡片”页点几下，确保 /events 正常写入。
        </div>
      </div>
    </main>
  );
}
