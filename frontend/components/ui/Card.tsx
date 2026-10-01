import { cn } from "@/lib/cn";

type CardProps = React.HTMLAttributes<HTMLDivElement> & {
  /** Soft lift + border highlight on hover. Default true. */
  interactive?: boolean;
};

export function Card({
  className,
  children,
  interactive = true,
  ...props
}: CardProps) {
  return (
    <div
      className={cn(
        "ui-card relative rounded-xl border border-border bg-surface p-5 shadow-card",
        interactive && "ui-card-interactive",
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}
