"use client";

import { X } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/cn";

export function TagInput({
  value,
  onChange,
  placeholder,
  className,
}: {
  value: string[];
  onChange: (tags: string[]) => void;
  placeholder?: string;
  className?: string;
}) {
  const [draft, setDraft] = useState("");

  function commit(raw: string) {
    const tag = raw.trim();
    if (!tag || value.includes(tag)) return;
    onChange([...value, tag]);
  }

  return (
    <div
      className={cn(
        "flex min-h-9 w-full flex-wrap items-center gap-1.5 rounded-lg border border-border bg-surface px-2 py-1.5",
        "focus-within:border-accent focus-within:ring-2 focus-within:ring-accentSoft",
        className
      )}
    >
      {value.map((tag) => (
        <span
          key={tag}
          className="flex items-center gap-1 rounded-full bg-accentSoft px-2 py-0.5 text-xs font-medium text-accent"
        >
          {tag}
          <button
            type="button"
            onClick={() => onChange(value.filter((t) => t !== tag))}
            className="rounded-full hover:opacity-70"
            aria-label={`Remove ${tag}`}
          >
            <X className="h-3 w-3" />
          </button>
        </span>
      ))}
      <input
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === ",") {
            e.preventDefault();
            commit(draft);
            setDraft("");
          } else if (e.key === "Backspace" && !draft && value.length > 0) {
            onChange(value.slice(0, -1));
          }
        }}
        onBlur={() => {
          if (draft) {
            commit(draft);
            setDraft("");
          }
        }}
        placeholder={value.length === 0 ? placeholder : undefined}
        className="min-w-[100px] flex-1 bg-transparent px-1 text-base text-fg placeholder:text-fgSubtle focus:outline-none"
      />
    </div>
  );
}
