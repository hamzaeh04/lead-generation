"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/cn";

/** Click-to-rename, same UX as renaming a file/folder in macOS Finder:
 * click the text to turn it into a selected-all text field, Enter or
 * clicking away saves, Escape reverts. Stops propagation on every
 * interaction so this can sit inside a clickable row (e.g. a <Link>
 * wrapping a list item) without triggering navigation. */
export function InlineEditableText({
  value,
  onSave,
  className,
  inputClassName,
  as: Tag = "span",
}: {
  value: string;
  onSave: (next: string) => void | Promise<void>;
  className?: string;
  inputClassName?: string;
  as?: "span" | "h2" | "p";
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing) {
      inputRef.current?.focus();
      inputRef.current?.select();
    }
  }, [editing]);

  // Reflect a value that changed elsewhere (e.g. a refetch after saving)
  // while not actively editing — never stomp on an in-progress edit.
  useEffect(() => {
    if (!editing) setDraft(value);
  }, [value, editing]);

  function startEditing(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    setDraft(value);
    setEditing(true);
  }

  function commit() {
    const trimmed = draft.trim();
    setEditing(false);
    if (trimmed && trimmed !== value) {
      onSave(trimmed);
    } else {
      setDraft(value);
    }
  }

  function cancel() {
    setDraft(value);
    setEditing(false);
  }

  if (editing) {
    return (
      <input
        ref={inputRef}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onClick={(e) => e.stopPropagation()}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            commit();
          } else if (e.key === "Escape") {
            e.preventDefault();
            cancel();
          }
        }}
        className={cn(
          "rounded border border-accent bg-surface px-1 -mx-1 outline-none ring-2 ring-accentSoft",
          inputClassName ?? className
        )}
      />
    );
  }

  return (
    <Tag
      onClick={startEditing}
      title="Click to rename"
      className={cn("cursor-text rounded px-1 -mx-1 transition-colors hover:bg-surface2", className)}
    >
      {value}
    </Tag>
  );
}
