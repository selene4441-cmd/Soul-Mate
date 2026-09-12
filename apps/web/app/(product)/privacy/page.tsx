"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { apiFetch, postJson } from "@/lib/api";
import { CONSENT_SCOPES } from "@/lib/consent";

type Consent = { id: string; scope: string; version: string; purpose: string; revoked_at: string | null };

export default function PrivacyPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const consents = useQuery({ queryKey: ["consents"], queryFn: () => apiFetch<Consent[]>("/consents") });
  const active = new Map(consents.data?.filter((item) => !item.revoked_at).map((item) => [item.scope, item]));

  const toggle = useMutation({
    mutationFn: async ({ scope, granted }: { scope: string; granted: boolean }) => {
      if (granted) {
        const item = CONSENT_SCOPES.find((entry) => entry.scope === scope);
        return postJson("/consents", { scope, purpose: item?.purpose });
      }
      return apiFetch(`/consents/${scope}`, { method: "DELETE" });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["consents"] }),
  });

  const deleteAccount = useMutation({
    mutationFn: () => apiFetch("/privacy/me", { method: "DELETE" }),
    onSuccess: () => router.replace("/"),
  });

  return (
    <div className="mx-auto max-w-4xl pb-20">
      <p className="eyebrow">数据与授权</p>
      <h1 className="mt-3 text-3xl font-semibold sm:text-4xl">你可以决定数据怎样被使用</h1>
      <p className="muted mt-4 leading-7">
        撤回授权后，系统会停止将对应数据用于匹配；删除账号会移除原始记录、Evidence、Claim、缓存引用和派生关系数据，
        仅保留不含正文的审计墓碑。
      </p>

      <div className="mt-8 space-y-4">
        {CONSENT_SCOPES.map((item) => {
          const granted = active.has(item.scope);
          return (
            <article key={item.scope} className="panel flex flex-col justify-between gap-5 sm:flex-row sm:items-center">
              <div>
                <div className="flex items-center gap-3">
                  <h2 className="text-xl font-semibold">{item.title}</h2>
                  <span className="chip">{granted ? "已授权" : "未授权"}</span>
                </div>
                <p className="muted mt-3 max-w-2xl text-sm leading-6">{item.purpose}</p>
              </div>
              <button
                className={granted ? "button-secondary shrink-0" : "button-primary shrink-0"}
                onClick={() => toggle.mutate({ scope: item.scope, granted: !granted })}
                disabled={toggle.isPending}
              >
                {granted ? "撤回授权" : "重新授权"}
              </button>
            </article>
          );
        })}
      </div>

      <section className="panel mt-8">
        <h2 className="text-2xl font-semibold">数据处理原则</h2>
        <ul className="muted mt-4 list-disc space-y-3 pl-5 leading-7">
          <li>未授权数据默认拒绝进入匹配链路。</li>
          <li>原始自述与最终排序隔离，只有经过确认的 Claim 参与规则匹配。</li>
          <li>不推断健康、宗教、性取向、政治倾向等敏感属性。</li>
          <li>不导入未经明确授权的第三方聊天或通讯录。</li>
          <li>安全事件和硬约束优先于普通关系线索。</li>
        </ul>
      </section>

      <section className="mt-8 rounded-[1.75rem] border border-[rgba(191,114,86,0.45)] bg-[rgba(191,114,86,0.06)] p-6 sm:p-8">
        <h2 className="text-2xl font-semibold">删除账号与派生数据</h2>
        <p className="muted mt-3 max-w-2xl leading-7">
          删除后无法继续登录，关系信号、证据、授权、会话、匹配和消息正文将被移除。此操作不可撤销。
        </p>
        <button
          className="mt-6 rounded-full bg-[var(--clay)] px-5 py-3 font-semibold text-white"
          onClick={() => {
            if (window.confirm("确认删除账号和全部派生数据吗？")) deleteAccount.mutate();
          }}
          disabled={deleteAccount.isPending}
        >
          {deleteAccount.isPending ? "正在删除…" : "删除账号与数据"}
        </button>
      </section>

      <Link href="/home" className="button-secondary mt-8">返回关系线索</Link>
    </div>
  );
}