"use client";

import { Eye, EyeOff } from "lucide-react";
import { type InputHTMLAttributes, forwardRef, useState } from "react";
import { cn } from "@/lib/cn";
import { Input } from "@/components/ui/Input";

export const PasswordInput = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => {
    const [visible, setVisible] = useState(false);
    return (
      <div className="relative">
        <Input ref={ref} type={visible ? "text" : "password"} className={cn("pr-9", className)} {...props} />
        <button
          type="button"
          tabIndex={-1}
          onClick={() => setVisible((v) => !v)}
          aria-label={visible ? "Hide password" : "Show password"}
          className="absolute inset-y-0 right-0 flex w-9 items-center justify-center text-fgSubtle transition-colors hover:text-fg"
        >
          {visible ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
        </button>
      </div>
    );
  }
);
PasswordInput.displayName = "PasswordInput";
