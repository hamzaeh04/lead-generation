import { type LucideIcon, TrendingDown, TrendingUp } from "lucide-react";
import { cn } from "@/lib/cn";
import { Card } from "@/components/ui/Card";

export function StatCard({
  label,
  value,
  hint,
  icon: Icon,
  trend,
  className,
}: {
  label: string;
  value: React.ReactNode;
  hint?: string;
  icon?: LucideIcon;
  /** Positive = good (green), negative = bad (red), omit for neutral. */
  trend?: number;
  className?: string;
}) {
  return (
    <Card className={cn("flex flex-col gap-2 p-4", className)}>
      <div className="flex items-center justify-between">
        <span className="text-sm text-fgMuted">{label}</span>
        {Icon && <Icon className="h-4 w-4 text-fgSubtle" />}
      </div>
      <div className="flex items-end justify-between gap-2">
        <span className="font-mono text-3xl font-semibold tabular-nums text-fg">{value}</span>
        {trend !== undefined && (
          <span
            className={cn(
              "mb-1 flex items-center gap-0.5 text-xs font-medium",
              trend >= 0 ? "text-success" : "text-danger"
            )}
          >
            {trend >= 0 ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
            {Math.abs(trend)}%
          </span>
        )}
      </div>
      {hint && <span className="text-xs text-fgSubtle">{hint}</span>}
    </Card>
  );
}
