"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useMe } from "@/lib/auth";

const NAV = [
  { href: "/home", label: "关系线索" },
  { href: "/messages", label: "交流" },
  { href: "/outcomes", label: "结果反馈" },
  { href: "/privacy", label: "数据与授权" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { data: user, isLoading } = useMe();

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-[var(--line)] bg-[rgba(245,242,233,0.9)] backdrop-blur-xl">
        <div className="shell flex min-h-16 items-center justify-between gap-4 py-3">
          <Link href="/home" className="flex items-center gap-3 font-semibold">
            <span className="grid h-9 w-9 place-items-center rounded-full bg-[var(--moss)] text-white">同</span>
            <span>同频</span>
          </Link>
          <nav aria-label="主要导航" className="hidden items-center gap-1 md:flex">
            {NAV.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={`rounded-full px-3 py-2 text-sm ${
                  pathname === item.href ? "bg-white font-semibold" : "muted"
                }`}
              >
                {item.label}
              </Link>
            ))}
          </nav>
          <div className="text-right text-sm">
            <div className="font-semibold">{isLoading ? "正在确认…" : user?.display_name}</div>
            <div className="muted hidden text-xs sm:block">信号可以随时修正</div>
          </div>
        </div>
      </header>
      <main className="shell py-8 sm:py-12">{children}</main>
      <nav className="fixed inset-x-3 bottom-3 z-20 grid grid-cols-4 rounded-3xl border border-[var(--line)] bg-[rgba(255,253,247,0.96)] p-2 shadow-lg backdrop-blur md:hidden">
        {NAV.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={`rounded-2xl px-1 py-2 text-center text-xs ${
              pathname === item.href ? "bg-[var(--moss)] text-white" : "muted"
            }`}
          >
            {item.label}
          </Link>
        ))}
      </nav>
    </div>
  );
}
