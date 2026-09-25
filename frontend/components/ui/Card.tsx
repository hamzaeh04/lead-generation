"use client";

import { useCallback, useRef, useState } from "react";
import { cn } from "@/lib/cn";

type CardProps = React.HTMLAttributes<HTMLDivElement> & {
  /** Soft 3D lift + pointer tilt on hover. Default true. */
  interactive?: boolean;
};

export function Card({
  className,
  children,
  interactive = true,
  onMouseMove,
  onMouseLeave,
  style,
  ...props
}: CardProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [tilt, setTilt] = useState({ x: 0, y: 0, glareX: 50, glareY: 50, active: false });

  const handleMove = useCallback(
    (event: React.MouseEvent<HTMLDivElement>) => {
      onMouseMove?.(event);
      if (!interactive || !ref.current) return;
      const rect = ref.current.getBoundingClientRect();
      const px = (event.clientX - rect.left) / rect.width;
      const py = (event.clientY - rect.top) / rect.height;
      // Subtle tilt — enough depth without feeling gimmicky on dense dashboards.
      setTilt({
        x: (py - 0.5) * -8,
        y: (px - 0.5) * 10,
        glareX: px * 100,
        glareY: py * 100,
        active: true,
      });
    },
    [interactive, onMouseMove]
  );

  const handleLeave = useCallback(
    (event: React.MouseEvent<HTMLDivElement>) => {
      onMouseLeave?.(event);
      if (!interactive) return;
      setTilt({ x: 0, y: 0, glareX: 50, glareY: 50, active: false });
    },
    [interactive, onMouseLeave]
  );

  return (
    <div
      ref={ref}
      className={cn(
        "card-3d relative rounded-xl border border-border bg-surface p-5 shadow-card",
        interactive && "card-3d-interactive",
        className
      )}
      style={{
        ...style,
        ...(interactive
          ? {
              transform: tilt.active
                ? `perspective(900px) rotateX(${tilt.x}deg) rotateY(${tilt.y}deg) translateY(-4px) scale(1.015)`
                : undefined,
              ["--glare-x" as string]: `${tilt.glareX}%`,
              ["--glare-y" as string]: `${tilt.glareY}%`,
            }
          : undefined),
      }}
      onMouseMove={handleMove}
      onMouseLeave={handleLeave}
      {...props}
    >
      {interactive && <span aria-hidden className="card-3d-glare" />}
      {children}
    </div>
  );
}
