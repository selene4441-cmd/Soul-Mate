import { NextResponse } from "next/server";

type EventsPayload = {
  events: Array<{
    user_id: number;
    event_type: string;
    target_id?: string | null;
    duration_ms: number;
  }>;
};

export async function POST(req: Request) {
  const baseUrl = process.env.API_BASE_URL ?? "http://127.0.0.1:8000";
  const body = (await req.json()) as EventsPayload;

  const resp = await fetch(`${baseUrl}/events`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store"
  });

  const text = await resp.text();
  return new NextResponse(text, {
    status: resp.status,
    headers: { "content-type": resp.headers.get("content-type") ?? "application/json" }
  });
}

