"use client";

import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import { useMe } from "@/lib/auth";

type SafetyEvent = {
  id: string;
  event_type: string;
  severity: string;
  status: string;
  created_at: string;
};
type Versions = { models: Array<{ id: string; description: string }>; policies: Array<{ id: string; description: string }> };

export default function AdminPage() {
  const { data: user } = useMe();
  const isAdmin = user?.role === "admin";
  const events = useQuery({
    queryKey: ["admin", "safety"],
    queryFn: () => apiFetch<SafetyEvent[]>("/admin/safety-events"),
    enabled: isAdmin,
  });
  const versions = useQuery({
    queryKey: ["admin", "versions"],
    queryFn: () => apiFetch<Versions>("/admin/versions"),
    enabled: isAdmin,
  });

  if (!isAdmin) {
    return <section className="panel"><h1 className="text-2xl font-semibold">当前账号没有管理权限</h1></section>;
  }

  return (
    <div className="pb-20">
      <p className="eyebrow">运营审核</p>
      <h1 className="mt-3 text-3xl font-semibold">安全事件与版本记录</h1>
      <div className="mt-8 grid gap-5 lg:grid-cols-2">
        <section className="panel">
          <h2 className="text-xl font-semibold">待审核安全事件</h2>
          <div className="mt-4 space-y-3">
            {events.data?.map((event) => (
              <article key={event.id} className="signal-card signal-difference">
                <p className="font-semibold">{event.event_type}</p>
                <p className="muted mt-2 text-sm">级别：{event.severity} · 状态：{event.status}</p>
              </article>
            ))}
            {!events.data?.length ? <p className="muted text-sm">当前没有事件。</p> : null}
          </div>
        </section>
        <section className="panel">
          <h2 className="text-xl font-semibold">当前版本</h2>
          <h3 className="mt-5 font-medium">模型</h3>
          {versions.data?.models.map((item) => <p key={item.id} className="muted mt-2 text-sm">{item.id} · {item.description}</p>)}
          <h3 className="mt-5 font-medium">曝光策略</h3>
          {versions.data?.policies.map((item) => <p key={item.id} className="muted mt-2 text-sm">{item.id} · {item.description}</p>)}
        </section>
      </div>
    </div>
  );
}