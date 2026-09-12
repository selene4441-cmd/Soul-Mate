"use client";

import { useEffect, useMemo, useState } from "react";
import { logClick } from "../../lib/events";
import { useUserId } from "../../lib/user";

type Msg = { role: "me" | "bot"; text: string };

export default function ChatPage() {
  const [userId] = useUserId();
  const [text, setText] = useState<string>("");
  const [msgs, setMsgs] = useState<Msg[]>([
    { role: "bot", text: "说一句话，我会把你的点击上报 /events。" }
  ]);

  const canSend = useMemo(() => text.trim().length > 0, [text]);

  useEffect(() => {
    void logClick({ userId, eventType: "browse", targetId: "page:chat", durationMs: 0 });
  }, [userId]);

  async function send() {
    const content = text.trim();
    if (!content) return;
    setText("");
    setMsgs((m) => [...m, { role: "me", text: content }]);

    await logClick({
      userId,
      eventType: "like",
      targetId: "chat:send",
      durationMs: 0
    });

    setMsgs((m) => [
      ...m,
      { role: "bot", text: "收到（此页暂不调用 LLM，仅记录事件）。" }
    ]);
  }

  return (
    <main className="container">
      <div className="row">
        <div>
          <div style={{ fontSize: 18, fontWeight: 700 }}>极简对话</div>
          <div className="muted" style={{ marginTop: 6, fontSize: 13 }}>
            发送与快捷按钮均会上报 /events。
          </div>
        </div>
      </div>

      <div style={{ height: 14 }} />
      <div className="card">
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {msgs.map((m, idx) => (
            <div
              key={idx}
              style={{
                alignSelf: m.role === "me" ? "flex-end" : "flex-start",
                maxWidth: "92%",
                padding: "10px 12px",
                borderRadius: 14,
                background:
                  m.role === "me"
                    ? "rgba(66,153,225,0.22)"
                    : "rgba(255,255,255,0.06)",
                border: "1px solid rgba(255,255,255,0.10)"
              }}
            >
              {m.text}
            </div>
          ))}
        </div>

        <div className="btnRow" style={{ marginTop: 16 }}>
          <button
            className="btn"
            onClick={() =>
              void logClick({
                userId,
                eventType: "browse",
                targetId: "chat:quick:hi",
                durationMs: 0
              }).then(() => {
                setText("你好");
              })
            }
          >
            你好
          </button>
          <button
            className="btn"
            onClick={() =>
              void logClick({
                userId,
                eventType: "browse",
                targetId: "chat:quick:why",
                durationMs: 0
              }).then(() => {
                setText("你觉得我更像哪种人？");
              })
            }
          >
            给我画像
          </button>
        </div>

        <div style={{ display: "flex", gap: 10, marginTop: 12 }}>
          <input
            className="input"
            style={{ flex: 1, width: "auto" }}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="输入一句话…"
          />
          <button className="navBtn" disabled={!canSend} onClick={() => void send()}>
            发送
          </button>
        </div>
      </div>
    </main>
  );
}
