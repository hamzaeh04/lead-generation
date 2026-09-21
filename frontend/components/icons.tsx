// The one hand-drawn mark that isn't in the lucide-react icon set — every
// other icon in the app comes straight from lucide-react.
import type { SVGProps } from "react";

export function LogoMarkIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 16 16" fill="none" strokeWidth={1.3} strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M2 8L6 4M6 4L14 4M6 4L6 12M14 4L10 8M14 4V12L10 8" stroke="currentColor" />
    </svg>
  );
}
