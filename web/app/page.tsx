"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { logClick } from "../lib/events";
import { useUserId } from "../lib/user";

type Card = {
  id: string;
  text: string;
};

const seedCards: Card[] = [
  { id: "c1", text: "我猜：你更在意被认真对待，而不是空泛的浪漫。" },
  { id: "c2", text: "我猜：你对边界很敏感，讨厌被催促或被逼表态。" },
  { id: "c3", text: "我可能错了：你会先观察很久，再决定是否投入。" }
];

export default function CardsPage() {
  const [userId, setUserId] = useUserId();
  const [index, setIndex] = useState<number>(0);
  const startedAtRef = useRef<number>(Date.now());

  const card = useMemo<Card>(() => seedCards[index % seedCards.length], [index]);

  useEffect(() => {
    void logClick({ userId, eventType: "browse", targetId: "page:cards", durationMs: 0 });
  }, [userId]);

  function nextCard() {
    setIndex((i) => i + 1);
    startedAtRef.current = Date.now();
  }

  async function vote(kind: "yes" | "no" | "skip") {
    const durationMs = Math.max(0, Date.now() - startedAtRef.current);
    const targetId = `card:${card.id}`;
    const eventType =
      kind === "yes" ? "like" : kind === "no" ? "swipe" : "browse";

    await logClick({
      userId,
      eventType,
      targetId,
      durationMs
    });
    nextCard();
  }

  return (
    <main className="container">
      <div className="row">
        <div>
          <div style={{ fontSize: 18, fontWeight: 700 }}>卡片流</div>
          <div className="muted" style={{ marginTop: 6, fontSize: 13 }}>
            任何点击都会上报到 /events（经 Next.js 代理）。
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span className="muted" style={{ fontSize: 12 }}>
            user_id
          </span>
          <input
            className="input"
            inputMode="numeric"
            value={String(userId)}
            onChange={(e) => setUserId(Number(e.target.value || "0"))}
          />
        </div>
      </div>

      <div style={{ height: 14 }} />
      <div className="card">
        <div className="muted" style={{ fontSize: 12 }}>
          {card.id}
        </div>
        <div style={{ fontSize: 20, lineHeight: 1.4, marginTop: 10 }}>
          {card.text}
        </div>
        <div className="btnRow">
          <button className="btn btnPrimary" onClick={() => void vote("yes")}>
            是
          </button>
          <button className="btn btnDanger" onClick={() => void vote("no")}>
            不是
          </button>
          <button className="btn" onClick={() => void vote("skip")}>
            跳过
          </button>
        </div>
      </div>
    </main>
  );
}
