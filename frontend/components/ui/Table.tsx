import { cn } from "@/lib/cn";

export function Table({ children }: { children: React.ReactNode }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-border bg-surface shadow-card">
      <table className="w-full border-collapse text-[13px]">{children}</table>
    </div>
  );
}

export function TableHead({ children }: { children: React.ReactNode }) {
  return (
    <thead>
      <tr className="border-b border-border bg-surface2 text-[10.5px] font-semibold uppercase tracking-wide text-fgMuted">
        {children}
      </tr>
    </thead>
  );
}

export function Th({ children, className, style }: React.ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th className={cn("px-4 py-2.5 text-left font-semibold", className)} style={style}>
      {children}
    </th>
  );
}

export function TableBody({ children }: { children: React.ReactNode }) {
  return <tbody>{children}</tbody>;
}

export function Tr({
  children,
  className,
  ...props
}: React.HTMLAttributes<HTMLTableRowElement>) {
  return (
    <tr
      className={cn("border-b border-border last:border-0 hover:bg-surface2", className)}
      {...props}
    >
      {children}
    </tr>
  );
}

export function Td({ children, className }: { children: React.ReactNode; className?: string }) {
  return <td className={cn("whitespace-nowrap px-4 py-3 align-middle text-fg", className)}>{children}</td>;
}
