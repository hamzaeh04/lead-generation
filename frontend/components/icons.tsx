// Small geometric line icons, matching the shell's design system.
// Kept together (not one file per icon) since they're single-purpose and
// only ever used by AppShell/nav — a folder-per-icon would be premature.
import type { SVGProps } from "react";

function Icon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 16 16"
      fill="none"
      strokeWidth={1.3}
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    />
  );
}

export function DashboardIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <rect x="2" y="2" width="5" height="5" rx="1" stroke="currentColor" />
      <rect x="9" y="2" width="5" height="5" rx="1" stroke="currentColor" />
      <rect x="2" y="9" width="5" height="5" rx="1" stroke="currentColor" />
      <rect x="9" y="9" width="5" height="5" rx="1" stroke="currentColor" />
    </Icon>
  );
}

export function CompaniesIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <rect x="2.5" y="4" width="11" height="9" rx="1.2" stroke="currentColor" />
      <path d="M2.5 6.5H13.5" stroke="currentColor" />
    </Icon>
  );
}

export function LeadsIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <circle cx="8" cy="5.5" r="2.5" stroke="currentColor" />
      <path d="M3 13.5C3 10.7 5.2 9 8 9C10.8 9 13 10.7 13 13.5" stroke="currentColor" />
    </Icon>
  );
}

export function DiscoverIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <circle cx="7" cy="7" r="4.5" stroke="currentColor" />
      <path d="M10.3 10.3L13.5 13.5" stroke="currentColor" />
    </Icon>
  );
}

export function CampaignsIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="M2 4L14 4M2 4L5 8L2 12M14 4L11 8L14 12M6 12H10" stroke="currentColor" />
    </Icon>
  );
}

export function SuppressionsIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path
        d="M2 3.5H14M4 3.5V12.5C4 13 4.4 13.5 5 13.5H11C11.6 13.5 12 13 12 12.5V3.5M6.5 6.5V10.5M9.5 6.5V10.5"
        stroke="currentColor"
      />
    </Icon>
  );
}

export function IcpIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path
        d="M8 2L9.8 5.8L14 6.4L11 9.2L11.7 13.4L8 11.4L4.3 13.4L5 9.2L2 6.4L6.2 5.8L8 2Z"
        stroke="currentColor"
        strokeLinejoin="round"
      />
    </Icon>
  );
}

export function ProvidersIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="M8 2V8L11.5 10.5" stroke="currentColor" />
      <circle cx="8" cy="8" r="6" stroke="currentColor" />
    </Icon>
  );
}

export function EmailSetupIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <rect x="2" y="3.5" width="12" height="9" rx="1.2" stroke="currentColor" />
      <path d="M2.5 5L8 9L13.5 5" stroke="currentColor" />
    </Icon>
  );
}

export function SettingsIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <circle cx="8" cy="8" r="6" stroke="currentColor" />
      <path d="M8 5.3V8L9.8 9.3" stroke="currentColor" />
    </Icon>
  );
}

export function AdminIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path
        d="M8 2L2.5 4.5V8C2.5 11 4.8 13.3 8 14C11.2 13.3 13.5 11 13.5 8V4.5L8 2Z"
        stroke="currentColor"
        strokeLinejoin="round"
      />
    </Icon>
  );
}

export function ChevronDownIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 12 12" fill="none" width="12" height="12" {...props}>
      <path
        d="M3 4.5L6 7.5L9 4.5"
        stroke="currentColor"
        strokeWidth={1.3}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function SunIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <circle cx="8" cy="8" r="3" stroke="currentColor" />
      <path
        d="M8 1.5V3M8 13V14.5M14.5 8H13M3 8H1.5M12.4 3.6L11.3 4.7M4.7 11.3L3.6 12.4M12.4 12.4L11.3 11.3M4.7 4.7L3.6 3.6"
        stroke="currentColor"
      />
    </Icon>
  );
}

export function MoonIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path
        d="M13.5 9.5A5.8 5.8 0 1 1 6.5 2.5A4.7 4.7 0 0 0 13.5 9.5Z"
        stroke="currentColor"
        strokeLinejoin="round"
      />
    </Icon>
  );
}

export function SystemIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <rect x="2" y="3" width="12" height="8" rx="1" stroke="currentColor" />
      <path d="M6 13.5H10M8 11V13.5" stroke="currentColor" />
    </Icon>
  );
}

export function LogoMarkIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path
        d="M2 8L6 4M6 4L14 4M6 4L6 12M14 4L10 8M14 4V12L10 8"
        stroke="currentColor"
      />
    </Icon>
  );
}
