import { type LucideIcon } from "lucide-react";
import { cn } from "@/lib/cn";

export function EmptyState({
  title,
  description,
  action,
  icon: Icon,
  className,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
  icon?: LucideIcon;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-border px-6 py-16 text-center",
        className
      )}
    >
      {Icon && (
        <span className="flex h-10 w-10 items-center justify-center rounded-full bg-surface2 text-fgSubtle">
          <Icon className="h-5 w-5" />
        </span>
      )}
      <p className="text-md font-medium text-fg">{title}</p>
      {description && <p className="max-w-sm text-base text-fgMuted">{description}</p>}
      {action}
    </div>
  );
}
