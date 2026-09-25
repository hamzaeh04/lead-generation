import { type LucideIcon, TrendingDown, TrendingUp } from "lucide-react";
import { cn } from "@/lib/cn";
import { Card } from "@/components/ui/Card";

type Tone = "accent" | "success" | "warning" | "danger" | "muted";

const toneBadgeClasses: Record<Tone, string> = {
  accent: "bg-accentSoft text-accent",
  success: "bg-successSoft text-success",
  warning: "bg-warningSoft text-warning",
  danger: "bg-dangerSoft text-danger",
  muted: "bg-surface2 text-fgSubtle",
};

export function StatCard({
  label,
  value,
  hint,
  icon: Icon,
  trend,
  tone,
  className,
}: {
  label: string;
  value: React.ReactNode;
  hint?: string;
  icon?: LucideIcon;
  /** Positive = good (green), negative = bad (red), omit for neutral. */
  trend?: number;
  /** Colors the icon into a soft badge instead of the plain muted glyph —
   * omit to keep the original plain look (used by several other pages). */
  tone?: Tone;
  className?: string;
}) {
  return (
    <Card className={cn("flex flex-col gap-2 p-4", className)}>
      <div className="flex items-center justify-between">
        <span className="text-sm text-fgMuted">{label}</span>
        {Icon && (
          <span
            className={cn(
              tone
                ? cn("flex h-7 w-7 items-center justify-center rounded-lg", toneBadgeClasses[tone])
                : "text-fgSubtle"
            )}
          >
            <Icon className="h-4 w-4" />
          </span>
        )}
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
