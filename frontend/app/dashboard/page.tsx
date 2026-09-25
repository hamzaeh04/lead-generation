"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  Building2,
  DollarSign,
  Handshake,
  Mail,
  Percent,
  Search,
  Sparkles,
  Trophy,
  Users2,
} from "lucide-react";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { buttonVariants } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { DonutChart, DonutLegend, RadialGauge } from "@/components/ui/Chart";
import { CardSkeleton } from "@/components/ui/Skeleton";
import { StatCard } from "@/components/ui/StatCard";
import { getAnalyticsOverview } from "@/lib/api";
import { useWorkspace } from "@/lib/workspace-context";

function formatPercent(value: number | null): string {
  return value === null ? "—" : `${Math.round(value * 1000) / 10}%`;
}

function QuickLink({
  href,
  label,
  description,
  icon: Icon,
}: {
  href: string;
  label: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
}) {
  return (
    <Link
      href={href}
      className="group flex items-center gap-3.5 rounded-xl border border-border bg-surface p-4 shadow-card transition-all hover:-translate-y-0.5 hover:border-accent hover:shadow-popover"
    >
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-accentSoft text-accent">
        <Icon className="h-4.5 w-4.5" />
      </span>
      <span className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="text-base font-medium text-fg">{label}</span>
        <span className="truncate text-sm text-fgMuted">{description}</span>
      </span>
      <ArrowRight className="h-4 w-4 shrink-0 text-fgSubtle transition-transform group-hover:translate-x-0.5 group-hover:text-accent" />
    </Link>
  );
}

function FunnelStep({
  label,
  count,
  pctOfFirst,
  pctOfPrev,
  isFirst,
}: {
  label: string;
  count: number;
  pctOfFirst: number;
  pctOfPrev: number | null;
  isFirst: boolean;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-baseline justify-between text-sm">
        <span className="font-medium text-fg">{label}</span>
        <span className="font-mono tabular-nums text-fgMuted">
          {count.toLocaleString()}
          {!isFirst && pctOfPrev !== null && (
            <span className="ml-1.5 text-xs text-fgSubtle">({pctOfPrev}% of prior step)</span>
          )}
        </span>
      </div>
      <div className="h-2.5 w-full overflow-hidden rounded-full bg-surface2">
        <div
          className="h-full rounded-full bg-accent transition-[width] duration-500"
          style={{ width: `${Math.max(pctOfFirst, count > 0 ? 3 : 0)}%` }}
        />
      </div>
    </div>
  );
}

function DashboardContent() {
  const { activeWorkspace, currentUser } = useWorkspace();

  const overviewQuery = useQuery({
    queryKey: ["analytics-overview", activeWorkspace?.id],
    queryFn: () => getAnalyticsOverview(activeWorkspace!.id),
    enabled: !!activeWorkspace,
  });

  const displayName = currentUser?.full_name ?? currentUser?.email ?? "";
  const overview = overviewQuery.data;

  const funnelSteps = overview
    ? [
        { label: "Sent", count: overview.emails_sent },
        { label: "Delivered", count: overview.delivered },
        { label: "Opened", count: overview.opened },
        { label: "Clicked", count: overview.clicked },
        { label: "Replied", count: overview.replied },
      ]
    : [];
  const funnelFirst = funnelSteps[0]?.count ?? 0;

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-fg">
            Welcome back, {displayName.split(" ")[0] || "there"}
          </h1>
          <p className="mt-1 text-sm text-fgMuted">
            {activeWorkspace ? activeWorkspace.name : "No workspace selected"} — here&apos;s what&apos;s real
            right now.
          </p>
        </div>
        <Link href="/discover" className={buttonVariants({ variant: "primary" })}>
          <Search className="h-3.5 w-3.5" />
          Find leads
        </Link>
      </div>

      {overviewQuery.isLoading && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <CardSkeleton key={i} />
          ))}
        </div>
      )}

      {overview && (
        <>
          <section className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatCard label="Companies" value={overview.total_companies} icon={Building2} tone="accent" />
            <StatCard label="Contacts" value={overview.total_contacts} icon={Users2} tone="accent" />
            <StatCard
              label="Contactable"
              value={overview.verified_emails}
              icon={Mail}
              tone="success"
              hint="have an email on file"
            />
            <StatCard
              label="High-intent leads"
              value={overview.high_intent_leads}
              icon={Sparkles}
              tone="warning"
              hint="intent score ≥ 50"
            />
            <StatCard label="Meetings" value={overview.meetings} icon={Handshake} tone="accent" />
            <StatCard label="Won" value={overview.conversions} icon={Trophy} tone="success" />
            <StatCard label="Reply rate" value={formatPercent(overview.reply_rate)} icon={Percent} tone="muted" />
          </section>

          <section className="grid grid-cols-1 gap-4 lg:grid-cols-5">
            <Card className="flex flex-col gap-4 lg:col-span-3">
              <div className="flex items-center justify-between">
                <h2 className="text-base font-semibold text-fg">Outreach funnel</h2>
                {overview.emails_sent > 0 && (
                  <span className="font-mono text-xs text-fgSubtle">{funnelFirst.toLocaleString()} sent</span>
                )}
              </div>
              {overview.emails_sent > 0 ? (
                <div className="flex flex-col gap-4 py-1">
                  {funnelSteps.map((step, i) => (
                    <FunnelStep
                      key={step.label}
                      label={step.label}
                      count={step.count}
                      isFirst={i === 0}
                      pctOfFirst={funnelFirst > 0 ? Math.round((step.count / funnelFirst) * 100) : 0}
                      pctOfPrev={
                        i === 0 || funnelSteps[i - 1].count === 0
                          ? null
                          : Math.round((step.count / funnelSteps[i - 1].count) * 100)
                      }
                    />
                  ))}
                </div>
              ) : (
                <div className="flex flex-col items-center gap-2 py-10 text-center">
                  <span className="flex h-10 w-10 items-center justify-center rounded-full bg-surface2 text-fgSubtle">
                    <Mail className="h-4.5 w-4.5" />
                  </span>
                  <p className="text-sm text-fgMuted">
                    No emails sent yet — start a campaign to see delivery, opens, and replies here.
                  </p>
                </div>
              )}
              <div className="flex flex-wrap items-center justify-around gap-4 border-t border-border pt-4">
                <RadialGauge
                  value={overview.delivery_rate !== null ? overview.delivery_rate * 100 : 0}
                  label="Delivery"
                  color="accent"
                  size={88}
                />
                <RadialGauge
                  value={overview.reply_rate !== null ? overview.reply_rate * 100 : 0}
                  label="Reply"
                  color="success"
                  size={88}
                />
                <RadialGauge
                  value={overview.bounce_rate !== null ? overview.bounce_rate * 100 : 0}
                  label="Bounce"
                  color="danger"
                  size={88}
                />
                <div className="flex flex-col items-center gap-1">
                  <span className="flex h-[88px] w-[88px] flex-col items-center justify-center gap-0.5 rounded-full bg-surface2">
                    <DollarSign className="h-4 w-4 text-fgSubtle" />
                    <span className="font-mono text-base font-semibold text-fg">
                      ${overview.total_provider_cost.toFixed(0)}
                    </span>
                  </span>
                  <span className="text-[11px] text-fgSubtle">Spend</span>
                </div>
              </div>
            </Card>

            <Card className="flex flex-col gap-3 lg:col-span-2">
              <h2 className="text-base font-semibold text-fg">Top sources</h2>
              {overview.top_sources.length > 0 ? (
                <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-center">
                  <div className="w-full max-w-[180px] shrink-0">
                    <DonutChart
                      data={overview.top_sources.map((s) => ({ provider: s.provider, count: s.count }))}
                      dataKey="count"
                      nameKey="provider"
                      height={180}
                    />
                  </div>
                  <div className="w-full min-w-0 flex-1">
                    <DonutLegend
                      data={overview.top_sources.map((s) => ({ provider: s.provider, count: s.count }))}
                      dataKey="count"
                      nameKey="provider"
                    />
                  </div>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-2 py-10 text-center">
                  <span className="flex h-10 w-10 items-center justify-center rounded-full bg-surface2 text-fgSubtle">
                    <Building2 className="h-4.5 w-4.5" />
                  </span>
                  <p className="text-sm text-fgMuted">No companies sourced yet.</p>
                </div>
              )}
            </Card>
          </section>

          {overview.top_campaigns.length > 0 && (
            <section className="flex flex-col gap-3">
              <h2 className="text-base font-semibold text-fg">Top campaigns</h2>
              <Card className="flex flex-col divide-y divide-border p-0">
                {overview.top_campaigns.map((c) => {
                  const openRate = c.sent > 0 ? Math.round((c.opened / c.sent) * 100) : null;
                  const replyRate = c.sent > 0 ? Math.round((c.replied / c.sent) * 100) : null;
                  return (
                    <div key={c.campaign_id} className="flex items-center justify-between gap-4 px-4 py-3.5">
                      <div className="flex min-w-0 items-center gap-3">
                        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accentSoft text-accent">
                          <Mail className="h-3.5 w-3.5" />
                        </span>
                        <span className="truncate text-base font-medium text-fg">{c.name}</span>
                      </div>
                      <div className="flex shrink-0 items-center gap-4 font-mono text-sm tabular-nums text-fgMuted">
                        <span>{c.sent} sent</span>
                        <span>{openRate !== null ? `${openRate}% open` : "—"}</span>
                        <span>{replyRate !== null ? `${replyRate}% reply` : "—"}</span>
                      </div>
                    </div>
                  );
                })}
              </Card>
            </section>
          )}
        </>
      )}

      <section className="flex flex-col gap-3">
        <h2 className="text-base font-semibold text-fg">Quick actions</h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <QuickLink href="/discover" label="Find leads" description="Apollo or Smartlead, AI prompt or filters" icon={Search} />
          <QuickLink href="/leads" label="Review leads" description="Check score and intent" icon={Users2} />
          <QuickLink href="/campaigns" label="Start outreach" description="Build a sequence" icon={Mail} />
        </div>
      </section>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <AppShell title="Dashboard">
      <DashboardContent />
    </AppShell>
  );
}
