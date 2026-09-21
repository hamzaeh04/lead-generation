"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/cn";

const items = [
  { href: "/settings/workspace", label: "Workspace" },
  { href: "/settings/workspaces", label: "All workspaces" },
];

export function SettingsNav() {
  const pathname = usePathname();
  return (
    <div className="inline-flex h-9 items-center gap-1 rounded-lg border border-border bg-surface2 p-1">
      {items.map((item) => {
        const active = pathname === item.href;
        return (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "inline-flex items-center justify-center whitespace-nowrap rounded-md px-3 py-1 text-base font-medium text-fgMuted transition-all",
              active && "bg-surface text-fg shadow-card"
            )}
          >
            {item.label}
          </Link>
        );
      })}
    </div>
  );
}
