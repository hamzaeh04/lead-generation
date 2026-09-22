"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { logout } from "@/lib/api";
import { useTheme } from "@/lib/theme";
import { useWorkspace } from "@/lib/workspace-context";
import {
  AdminIcon,
  CampaignsIcon,
  ChevronDownIcon,
  CompaniesIcon,
  DashboardIcon,
  DiscoverIcon,
  EmailSetupIcon,
  LeadsIcon,
  LogoMarkIcon,
  MoonIcon,
  ProvidersIcon,
  SettingsIcon,
  SuppressionsIcon,
  SunIcon,
  SystemIcon,
} from "@/components/icons";
import { Spinner } from "@/components/ui/Spinner";
import { cn } from "@/lib/cn";

const primaryNav = [
  { href: "/dashboard", label: "Dashboard", icon: DashboardIcon },
  { href: "/companies", label: "Companies", icon: CompaniesIcon },
  { href: "/leads", label: "Leads", icon: LeadsIcon },
  { href: "/discover", label: "Discover", icon: DiscoverIcon },
  { href: "/campaigns", label: "Campaigns", icon: CampaignsIcon },
  { href: "/suppressions", label: "Suppressions", icon: SuppressionsIcon },
];

const configureNav = [
  { href: "/email-setup", label: "Email Setup", icon: EmailSetupIcon },
  { href: "/providers", label: "Providers", icon: ProvidersIcon },
  { href: "/settings/workspace", label: "Settings", icon: SettingsIcon },
];

function initials(name: string) {
  const parts = name.trim().split(/\s+/);
  const chars = parts.length > 1 ? [parts[0][0], parts[parts.length - 1][0]] : [name.slice(0, 2)];
  return chars.join("").toUpperCase();
}

function NavLink({
  href,
  label,
  icon: IconComponent,
  active,
}: {
  href: string;
  label: string;
  icon: (props: { className?: string }) => React.ReactNode;
  active: boolean;
}) {
  return (
    <Link
      href={href}
      className={cn(
        "flex items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-[13px] text-fgMuted hover:bg-surface2 hover:text-fg",
        active && "bg-accentSoft font-medium text-accent hover:bg-accentSoft hover:text-accent"
      )}
    >
      <IconComponent className="h-[15px] w-[15px] shrink-0 opacity-85" />
      {label}
    </Link>
  );
}

function ThemeToggle() {
  const { preference, cycleTheme } = useTheme();
  const Icon = preference === "light" ? SunIcon : preference === "dark" ? MoonIcon : SystemIcon;
  const label =
    preference === "light" ? "Light theme" : preference === "dark" ? "Dark theme" : "System theme";

  return (
    <button
      onClick={cycleTheme}
      title={`${label} — click to change`}
      aria-label={`Theme: ${label}. Click to change.`}
      className="flex h-7 w-7 items-center justify-center rounded-md border border-border text-fgMuted hover:bg-surface2 hover:text-fg"
    >
      <Icon className="h-3.5 w-3.5" />
    </button>
  );
}

export function AppShell({ children, title }: { children: React.ReactNode; title: string }) {
  const router = useRouter();
  const pathname = usePathname();
  const { currentUser, workspaces, activeWorkspace, setActiveWorkspaceId, authStatus, refreshAuth } =
    useWorkspace();

  useEffect(() => {
    if (authStatus === "unauthenticated") {
      router.replace("/login");
    }
  }, [authStatus, router]);

  if (authStatus !== "authenticated" || !currentUser) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bg">
        <Spinner />
      </div>
    );
  }

  const displayName = currentUser.full_name ?? currentUser.email;

  async function handleLogout() {
    await logout();
    refreshAuth();
    router.push("/login");
  }

  return (
    <div className="flex min-h-screen bg-bg text-fg">
      <aside className="sticky top-0 flex h-screen w-[236px] shrink-0 flex-col gap-5 border-r border-border p-3">
        <div className="flex items-center gap-2 px-2 py-1 text-[13.5px] font-semibold tracking-tight">
          <span className="flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded-md bg-accent text-white">
            <LogoMarkIcon className="h-[13px] w-[13px]" stroke="currentColor" />
          </span>
          Lead Intelligence
        </div>

        {workspaces.length > 0 && activeWorkspace && (
          <details className="group relative">
            <summary className="flex list-none items-center justify-between gap-2 rounded-lg border border-border bg-surface px-2.5 py-2 text-[12.5px] [&::-webkit-details-marker]:hidden">
              <span className="flex min-w-0 items-center gap-2">
                <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-success" />
                <span className="truncate font-medium">{activeWorkspace.name}</span>
              </span>
              <ChevronDownIcon className="shrink-0 text-fgMuted" />
            </summary>
            <div className="absolute left-0 right-0 top-[calc(100%+4px)] z-10 overflow-hidden rounded-lg border border-border bg-surface py-1 shadow-lg">
              {workspaces.map((ws) => (
                <button
                  key={ws.id}
                  onClick={(e) => {
                    setActiveWorkspaceId(ws.id);
                    (e.currentTarget.closest("details") as HTMLDetailsElement).open = false;
                  }}
                  className={cn(
                    "flex w-full items-center gap-2 px-2.5 py-1.5 text-left text-[12.5px] hover:bg-surface2",
                    ws.id === activeWorkspace.id && "text-accent"
                  )}
                >
                  <span className="truncate">{ws.name}</span>
                </button>
              ))}
              <Link
                href="/settings/workspaces"
                className="block border-t border-border px-2.5 py-1.5 text-[12.5px] text-fgMuted hover:bg-surface2 hover:text-fg"
              >
                Manage workspaces
              </Link>
            </div>
          </details>
        )}

        <nav className="flex flex-col gap-3.5 overflow-y-auto">
          <div className="flex flex-col gap-0.5">
            <div className="px-2.5 pb-1 text-[10.5px] font-semibold uppercase tracking-wider text-fgMuted">
              Workspace
            </div>
            {primaryNav.map((item) => (
              <NavLink key={item.href} {...item} active={pathname?.startsWith(item.href) ?? false} />
            ))}
          </div>
          <div className="flex flex-col gap-0.5">
            <div className="px-2.5 pb-1 text-[10.5px] font-semibold uppercase tracking-wider text-fgMuted">
              Configure
            </div>
            {configureNav.map((item) => (
              <NavLink key={item.href} {...item} active={pathname?.startsWith(item.href) ?? false} />
            ))}
            {currentUser.is_superuser && (
              <NavLink
                href="/admin"
                label="Admin"
                icon={AdminIcon}
                active={pathname?.startsWith("/admin") ?? false}
              />
            )}
          </div>
        </nav>

        <details className="group relative mt-auto">
          <summary className="flex list-none items-center gap-2 rounded-lg border-t border-border px-2 pt-3.5 [&::-webkit-details-marker]:hidden">
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-border bg-surface2 text-[10.5px] font-semibold text-fgMuted">
              {initials(displayName)}
            </span>
            <span className="min-w-0 flex-1 text-left text-[12px] leading-tight">
              <span className="block truncate font-medium text-fg">{displayName}</span>
              <span className="block truncate text-fgMuted">{currentUser.email}</span>
            </span>
          </summary>
          <div className="absolute bottom-[calc(100%+4px)] left-0 right-0 z-10 overflow-hidden rounded-lg border border-border bg-surface py-1 shadow-lg">
            <button
              onClick={handleLogout}
              className="w-full px-3 py-1.5 text-left text-[12.5px] text-fg hover:bg-surface2"
            >
              Log out
            </button>
          </div>
        </details>
      </aside>

      <div className="min-w-0 flex-1">
        <header className="sticky top-0 z-[5] flex h-14 items-center justify-between border-b border-border bg-bg/90 px-7 backdrop-blur">
          <span className="text-[13px] text-fgMuted">
            {title}
          </span>
          <ThemeToggle />
        </header>
        <main className="max-w-[1000px] px-7 py-9">{children}</main>
      </div>
    </div>
  );
}
