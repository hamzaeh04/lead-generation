import { ChevronRight } from "lucide-react";
import Link from "next/link";
import { Fragment } from "react";
import { cn } from "@/lib/cn";

export interface BreadcrumbItem {
  label: string;
  href?: string;
}

export function Breadcrumb({ items, className }: { items: BreadcrumbItem[]; className?: string }) {
  return (
    <nav className={cn("flex items-center gap-1.5 text-sm text-fgMuted", className)} aria-label="Breadcrumb">
      {items.map((item, i) => {
        const isLast = i === items.length - 1;
        return (
          <Fragment key={`${item.label}-${i}`}>
            {i > 0 && <ChevronRight className="h-3 w-3 shrink-0 text-fgSubtle" />}
            {item.href && !isLast ? (
              <Link href={item.href} className="truncate hover:text-fg">
                {item.label}
              </Link>
            ) : (
              <span className={cn("truncate", isLast && "font-medium text-fg")}>{item.label}</span>
            )}
          </Fragment>
        );
      })}
    </nav>
  );
}
