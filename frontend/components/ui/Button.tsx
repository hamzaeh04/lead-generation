import { type VariantProps, cva } from "class-variance-authority";
import { type ButtonHTMLAttributes, forwardRef } from "react";
import { cn } from "@/lib/cn";
import { Spinner } from "@/components/ui/Spinner";

export const buttonVariants = cva(
  "inline-flex shrink-0 items-center justify-center gap-2 rounded-lg font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50",
  {
    variants: {
      variant: {
        primary: "bg-accent text-white hover:opacity-90",
        secondary: "bg-surface2 text-fg hover:bg-border",
        ghost: "border border-border bg-surface text-fg hover:bg-surface2",
        outline: "border border-border bg-transparent text-fg hover:bg-surface2",
        danger: "bg-danger text-white hover:opacity-90",
        link: "text-accent underline-offset-4 hover:underline",
      },
      size: {
        sm: "h-7 px-2.5 text-xs",
        md: "h-9 px-3.5 text-base",
        lg: "h-10 px-5 text-md",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  }
);

interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  loading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, disabled, loading, children, ...props }, ref) => (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    >
      {loading && <Spinner className="h-3.5 w-3.5 border-current/30 border-t-current" />}
      {children}
    </button>
  )
);
Button.displayName = "Button";
