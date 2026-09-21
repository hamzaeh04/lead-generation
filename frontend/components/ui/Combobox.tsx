"use client";

import { Check, ChevronsUpDown, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { cn } from "@/lib/cn";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/Popover";

export interface ComboboxOption {
  value: string;
  label: string;
  description?: string;
}

export function Combobox({
  options,
  value,
  onChange,
  placeholder = "Select…",
  searchPlaceholder = "Search…",
  emptyText = "No results found.",
  disabled,
  className,
}: {
  options: ComboboxOption[];
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  searchPlaceholder?: string;
  emptyText?: string;
  disabled?: boolean;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    if (!query.trim()) return options;
    const q = query.trim().toLowerCase();
    return options.filter((o) => o.label.toLowerCase().includes(q));
  }, [options, query]);

  const selected = options.find((o) => o.value === value);

  return (
    <Popover
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) setQuery("");
      }}
    >
      <PopoverTrigger asChild>
        <button
          type="button"
          disabled={disabled}
          className={cn(
            "flex h-9 w-full items-center justify-between gap-2 rounded-lg border border-border bg-surface px-3 text-base text-fg transition-colors",
            "focus:border-accent focus:outline-none focus:ring-2 focus:ring-accentSoft",
            "disabled:cursor-not-allowed disabled:opacity-50",
            !selected && "text-fgSubtle",
            className
          )}
        >
          <span className="truncate">{selected ? selected.label : placeholder}</span>
          <ChevronsUpDown className="h-3.5 w-3.5 shrink-0 text-fgMuted" />
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-[--radix-popover-trigger-width] p-0">
        <div className="flex items-center gap-2 border-b border-border px-3">
          <Search className="h-3.5 w-3.5 shrink-0 text-fgSubtle" />
          <input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={searchPlaceholder}
            className="h-9 w-full bg-transparent text-base text-fg placeholder:text-fgSubtle focus:outline-none"
          />
        </div>
        <div className="max-h-64 overflow-y-auto p-1">
          {filtered.length === 0 ? (
            <p className="px-2 py-4 text-center text-sm text-fgSubtle">{emptyText}</p>
          ) : (
            filtered.map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() => {
                  onChange(option.value);
                  setOpen(false);
                  setQuery("");
                }}
                className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-base hover:bg-surface2"
              >
                <Check
                  className={cn(
                    "h-3.5 w-3.5 shrink-0 text-accent",
                    option.value === value ? "opacity-100" : "opacity-0"
                  )}
                />
                <span className="min-w-0 flex-1">
                  <span className="block truncate">{option.label}</span>
                  {option.description && (
                    <span className="block truncate text-xs text-fgSubtle">{option.description}</span>
                  )}
                </span>
              </button>
            ))
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
