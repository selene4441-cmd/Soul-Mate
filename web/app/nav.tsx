"use client";

import { usePathname, useRouter } from "next/navigation";
import { logClick } from "../lib/events";

type NavItem = {
  href: string;
  label: string;
  targetId: string;
};

const items: NavItem[] = [
  { href: "/", label: "卡片", targetId: "nav:cards" },
  { href: "/match", label: "匹配", targetId: "nav:match" },
  { href: "/chat", label: "对话", targetId: "nav:chat" }
];

export function Nav() {
  const router = useRouter();
  const pathname = usePathname();

  return (
    <div className="nav">
      <div className="navInner">
        {items.map((it) => (
          <button
            key={it.href}
            className="navBtn"
            onClick={() => {
              void logClick({ eventType: "browse", targetId: it.targetId, durationMs: 0 });
              if (pathname !== it.href) router.push(it.href);
            }}
            aria-current={pathname === it.href ? "page" : undefined}
          >
            {it.label}
          </button>
        ))}
      </div>
    </div>
  );
}

