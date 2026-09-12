"use client";

export type EventType = "browse" | "dwell" | "like" | "swipe";

export type EventIn = {
  userId?: number;
  eventType: EventType;
  targetId: string;
  durationMs: number;
};

function getUserIdFromStorage(): number {
  if (typeof window === "undefined") return 1;
  const raw = window.localStorage.getItem("soulmate:user_id");
  const parsed = Number(raw || "1");
  return Number.isFinite(parsed) && parsed >= 1 ? parsed : 1;
}

export async function logClick(input: EventIn): Promise<void> {
  const userId = input.userId ?? getUserIdFromStorage();
  const payload = {
    events: [
      {
        user_id: userId,
        event_type: input.eventType,
        target_id: input.targetId,
        duration_ms: input.durationMs
      }
    ]
  };

  // Prefer sendBeacon so navigation doesn't drop events.
  try {
    if (typeof navigator !== "undefined" && "sendBeacon" in navigator) {
      const ok = navigator.sendBeacon(
        "/api/events",
        new Blob([JSON.stringify(payload)], { type: "application/json" })
      );
      if (ok) return;
    }
  } catch {
    // ignore and fallback to fetch
  }

  try {
    await fetch("/api/events", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
      keepalive: true
    });
  } catch {
    // swallow: logging should never break UX
  }
}

