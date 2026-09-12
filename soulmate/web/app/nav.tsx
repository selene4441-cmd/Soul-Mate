"use client";

import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { postJson } from "../lib/api";

const items = [
  { href: "/", label: "首页" },
  { href: "/matches", label: "我的匹配" }
];

export function Nav() {
  const router = useRouter();
  const pathname = usePathname();
  const [busy, setBusy] = useState(false);

  async function logout() {
    setBusy(true);
    try {
      await postJson("/auth/logout");
    } catch {
      // 即使后端登出失败也要清掉本地界面状态
    } finally {
      setBusy(false);
      router.push("/");
      router.refresh();
    }
  }

  return (
    <div className="nav">
      <div className="navInner">
        {items.map((it) => (
          <button
            key={it.href}
            className="navBtn"
            aria-current={pathname === it.href ? "page" : undefined}
            onClick={() => {
              if (pathname !== it.href) router.push(it.href);
            }}
          >
            {it.label}
          </button>
        ))}
        <button className="navBtn" disabled={busy} onClick={() => void logout()}>
          {busy ? "退出中…" : "退出登录"}
        </button>
      </div>
    </div>
  );
}
