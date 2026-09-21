"use client";

import { Check } from "lucide-react";
import { cn } from "@/lib/cn";

export function MultiSelectChips({
  options,
  value,
  onChange,
  className,
}: {
  options: { value: string; label: string }[];
  value: string[];
  onChange: (value: string[]) => void;
  className?: string;
}) {
  function toggle(v: string) {
    onChange(value.includes(v) ? value.filter((x) => x !== v) : [...value, v]);
  }

  return (
    <div className={cn("flex flex-wrap gap-1.5", className)}>
      {options.map((option) => {
        const active = value.includes(option.value);
        return (
          <button
            key={option.value}
            type="button"
            onClick={() => toggle(option.value)}
            className={cn(
              "flex items-center gap-1 rounded-full border px-2.5 py-1.5 text-xs font-medium transition-all",
              active
                ? "border-accent bg-accent text-white shadow-sm"
                : "border-border bg-surface text-fgMuted hover:border-accent/40 hover:bg-surface2 hover:text-fg"
            )}
          >
            {active && <Check className="h-2.5 w-2.5" />}
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
