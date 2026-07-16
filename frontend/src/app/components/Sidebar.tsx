"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: "◉" },
  { href: "/copilot", label: "Copilot", icon: "✦" },
  { href: "/health", label: "Health", icon: "◆" },
  { href: "/evidence", label: "Evidence", icon: "▣" },
  { href: "/intelligence", label: "Intelligence", icon: "◎" },
  { href: "/portfolio", label: "Portfolio", icon: "▤" },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-56 bg-surface-alt border-r border-surface-border flex flex-col shrink-0">
      <div className="px-5 py-5 border-b border-surface-border">
        <Link href="/" className="text-lg font-bold text-fg tracking-tight">
          FIOS
        </Link>
        <p className="text-2xs text-fg-dim mt-0.5">intelligence platform</p>
      </div>
      <nav className="flex-1 py-3 px-2 space-y-0.5">
        {NAV_ITEMS.map((item) => {
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                active
                  ? "bg-surface-hover text-fg font-medium"
                  : "text-fg-dim hover:text-fg hover:bg-surface-hover"
              }`}
            >
              <span className="w-5 text-center text-xs">{item.icon}</span>
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="px-5 py-3 border-t border-surface-border text-2xs text-fg-faint">
        v0.1.0
      </div>
    </aside>
  );
}
