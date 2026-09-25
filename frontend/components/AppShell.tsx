"use client";

import {
  Check,
  ChevronsUpDown,
  LayoutDashboard,
  LogOut,
  Mail,
  Megaphone,
  Menu,
  Monitor,
  Moon,
  Plug,
  Search,
  Settings,
  ShieldCheck,
  ShieldOff,
  Sun,
  Users,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { LogoMarkIcon } from "@/components/icons";
import { Avatar, AvatarFallback, initials } from "@/components/ui/Avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/DropdownMenu";
import { Spinner } from "@/components/ui/Spinner";
import { logout } from "@/lib/api";
import { cn } from "@/lib/cn";
import { useTheme } from "@/lib/theme";
import { useWorkspace } from "@/lib/workspace-context";

const primaryNav = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/discover", label: "Discover", icon: Search },
  { href: "/leads", label: "Leads", icon: Users },
  { href: "/campaigns", label: "Campaigns", icon: Megaphone },
  { href: "/suppressions", label: "Suppressions", icon: ShieldOff },
];

const configureNav = [
  { href: "/email-setup", label: "Email Setup", icon: Mail },
  { href: "/providers", label: "Providers", icon: Plug },
  { href: "/settings/workspace", label: "Settings", icon: Settings },
];

function NavLink({
  href,
  label,
  icon: IconComponent,
  active,
  onNavigate,
}: {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  active: boolean;
  onNavigate?: () => void;
}) {
  return (
    <Link
      href={href}
      onClick={onNavigate}
      className={cn(
        "flex items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-base text-fgMuted transition-colors hover:bg-surface2 hover:text-fg",
        active && "bg-accentSoft font-medium text-accent hover:bg-accentSoft hover:text-accent"
      )}
    >
      <IconComponent className="h-[15px] w-[15px] shrink-0" />
      {label}
    </Link>
  );
}

function ThemeToggle() {
  const { preference, cycleTheme } = useTheme();
  const Icon = preference === "light" ? Sun : preference === "dark" ? Moon : Monitor;
  const label =
    preference === "light" ? "Light theme" : preference === "dark" ? "Dark theme" : "System theme";

  return (
    <button
      onClick={cycleTheme}
      title={`${label} — click to change`}
      aria-label={`Theme: ${label}. Click to change.`}
      className="flex h-8 w-8 items-center justify-center rounded-md border border-border text-fgMuted transition-colors hover:bg-surface2 hover:text-fg"
    >
      <Icon className="h-3.5 w-3.5" />
    </button>
  );
}

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const router = useRouter();
  const { currentUser, workspaces, activeWorkspace, setActiveWorkspaceId, refreshAuth } = useWorkspace();

  if (!currentUser) return null;
  const displayName = currentUser.full_name ?? currentUser.email;

  async function handleLogout() {
    await logout();
    refreshAuth();
    router.push("/login");
  }

  return (
    <div className="flex h-full flex-col gap-5 p-3">
      <div className="flex items-center gap-2 px-2 py-1 text-base font-semibold tracking-tight text-fg">
        <span className="flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded-md bg-accent text-white">
          <LogoMarkIcon className="h-[13px] w-[13px]" stroke="currentColor" />
        </span>
        Lead Intelligence
      </div>

      {workspaces.length > 0 && activeWorkspace && (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button className="flex items-center justify-between gap-2 rounded-lg border border-border bg-surface px-2.5 py-2 text-sm transition-colors hover:bg-surface2">
              <span className="flex min-w-0 items-center gap-2">
                <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-success" />
                <span className="truncate font-medium text-fg">{activeWorkspace.name}</span>
              </span>
              <ChevronsUpDown className="h-3.5 w-3.5 shrink-0 text-fgMuted" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-[210px]">
            <DropdownMenuLabel>Workspaces</DropdownMenuLabel>
            {workspaces.map((ws) => (
              <DropdownMenuItem key={ws.id} onClick={() => setActiveWorkspaceId(ws.id)}>
                <span className="min-w-0 flex-1 truncate">{ws.name}</span>
                {ws.id === activeWorkspace.id && <Check className="h-3.5 w-3.5 shrink-0 text-accent" />}
              </DropdownMenuItem>
            ))}
            <DropdownMenuSeparator />
            <DropdownMenuItem asChild>
              <Link href="/settings/workspaces" onClick={onNavigate}>
                Manage workspaces
              </Link>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      )}

      <nav className="flex flex-1 flex-col gap-3.5 overflow-y-auto">
        <div className="flex flex-col gap-0.5">
          <div className="px-2.5 pb-1 text-2xs font-semibold uppercase tracking-wider text-fgSubtle">
            Workspace
          </div>
          {primaryNav.map((item) => (
            <NavLink
              key={item.href}
              {...item}
              active={pathname?.startsWith(item.href) ?? false}
              onNavigate={onNavigate}
            />
          ))}
        </div>
        <div className="flex flex-col gap-0.5">
          <div className="px-2.5 pb-1 text-2xs font-semibold uppercase tracking-wider text-fgSubtle">
            Configure
          </div>
          {configureNav.map((item) => (
            <NavLink
              key={item.href}
              {...item}
              active={pathname?.startsWith(item.href) ?? false}
              onNavigate={onNavigate}
            />
          ))}
          {currentUser.is_superuser && (
            <NavLink
              href="/admin"
              label="Admin"
              icon={ShieldCheck}
              active={pathname?.startsWith("/admin") ?? false}
              onNavigate={onNavigate}
            />
          )}
        </div>
      </nav>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button className="flex items-center gap-2 rounded-lg border-t border-border px-2 pt-3.5 text-left transition-colors hover:bg-surface2">
            <Avatar className="h-6 w-6 border border-border">
              <AvatarFallback className="text-2xs">{initials(displayName)}</AvatarFallback>
            </Avatar>
            <span className="min-w-0 flex-1 text-left text-sm leading-tight">
              <span className="block truncate font-medium text-fg">{displayName}</span>
              <span className="block truncate text-xs text-fgMuted">{currentUser.email}</span>
            </span>
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" side="top" className="w-[210px]">
          <DropdownMenuItem destructive onClick={handleLogout}>
            <LogOut className="h-3.5 w-3.5" />
            Log out
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}

export function AppShell({
  children,
  title,
  description,
  actions,
  fullWidth,
}: {
  children: React.ReactNode;
  title: string;
  description?: string;
  actions?: React.ReactNode;
  /** Skip the default max-w-[1200px] content cap — for pages (like Discover)
   * that need the full viewport width rather than a centered column. */
  fullWidth?: boolean;
}) {
  const router = useRouter();
  const { currentUser, authStatus } = useWorkspace();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  useEffect(() => {
    if (authStatus === "unauthenticated") {
      router.replace("/login");
    }
  }, [authStatus, router]);

  useEffect(() => {
    setMobileNavOpen(false);
  }, [router]);

  if (authStatus !== "authenticated" || !currentUser) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bg">
        <Spinner />
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-bg text-fg">
      {/* Desktop sidebar */}
      <aside className="sticky top-0 hidden h-screen w-[236px] shrink-0 border-r border-border md:block">
        <SidebarContent />
      </aside>

      {/* Mobile slide-over sidebar */}
      {mobileNavOpen && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div className="absolute inset-0 bg-black/40" onClick={() => setMobileNavOpen(false)} />
          <div className="absolute left-0 top-0 h-full w-[260px] border-r border-border bg-bg shadow-popover animate-in slide-in-from-left">
            <button
              onClick={() => setMobileNavOpen(false)}
              className="absolute right-3 top-3 flex h-7 w-7 items-center justify-center rounded-md text-fgMuted hover:bg-surface2"
              aria-label="Close menu"
            >
              <X className="h-4 w-4" />
            </button>
            <SidebarContent onNavigate={() => setMobileNavOpen(false)} />
          </div>
        </div>
      )}

      <div className="min-w-0 flex-1">
        <header className="sticky top-0 z-[5] flex min-h-14 flex-wrap items-center justify-between gap-3 border-b border-border bg-bg/90 px-4 py-2.5 backdrop-blur sm:px-7">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setMobileNavOpen(true)}
              className="flex h-8 w-8 items-center justify-center rounded-md border border-border text-fgMuted hover:bg-surface2 md:hidden"
              aria-label="Open menu"
            >
              <Menu className="h-4 w-4" />
            </button>
            <div>
              <h1 className="text-md font-semibold text-fg">{title}</h1>
              {description && <p className="text-xs text-fgMuted">{description}</p>}
            </div>
          </div>
          <div className="flex items-center gap-2">
            {actions}
            <ThemeToggle />
          </div>
        </header>
        <main className={cn("px-4 py-6 sm:px-7 sm:py-9", fullWidth ? "w-full" : "mx-auto max-w-[1200px]")}>
          {children}
        </main>
      </div>
    </div>
  );
}
