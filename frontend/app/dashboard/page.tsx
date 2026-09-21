"use client";

import { useQuery } from "@tanstack/react-query";
import { Handshake, Mail, Search, Sparkles, Target, Trophy, Users2 } from "lucide-react";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { Card } from "@/components/ui/Card";
import { ComparisonBarChart } from "@/components/ui/Chart";
import { CardSkeleton, Skeleton } from "@/components/ui/Skeleton";
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
      className="flex items-start gap-3 rounded-xl border border-border bg-surface p-4 shadow-card transition-colors hover:border-accent"
    >
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accentSoft text-accent">
        <Icon className="h-4 w-4" />
      </span>
      <span className="flex flex-col gap-0.5">
        <span className="text-base font-medium text-fg">{label}</span>
        <span className="text-sm text-fgMuted">{description}</span>
      </span>
    </Link>
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

  const funnelData = overview
    ? [
        { label: "Sent", count: overview.emails_sent },
        { label: "Delivered", count: overview.delivered },
        { label: "Opened", count: overview.opened },
        { label: "Clicked", count: overview.clicked },
        { label: "Replied", count: overview.replied },
      ]
    : [];

  return (
    <div className="flex flex-col gap-9">
      <div>
        <p className="mt-1 text-sm text-fgMuted">
          Welcome back, {displayName.split(" ")[0]} —{" "}
          {activeWorkspace ? activeWorkspace.name : "no workspace selected"}, here&apos;s what&apos;s real
          right now.
        </p>
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
          <section className="flex flex-col gap-3">
            <h2 className="text-base font-semibold text-fg">Pipeline</h2>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <StatCard label="Companies" value={overview.total_companies} icon={Search} />
              <StatCard label="Contacts" value={overview.total_contacts} icon={Users2} />
              <StatCard label="Contactable" value={overview.verified_emails} icon={Mail} hint="have an email on file" />
              <StatCard
                label="High-intent leads"
                value={overview.high_intent_leads}
                icon={Sparkles}
                hint="intent score ≥ 50"
              />
              <StatCard label="Meetings" value={overview.meetings} icon={Handshake} />
              <StatCard label="Won" value={overview.conversions} icon={Trophy} />
              <StatCard
                label="High-fit leads"
                value={overview.high_icp_leads ?? "—"}
                icon={Target}
                hint={overview.high_icp_leads === null ? "select an ICP profile to compute" : "score ≥ 70"}
              />
              <StatCard label="Reply rate" value={formatPercent(overview.reply_rate)} />
            </div>
          </section>

          <section className="grid grid-cols-1 gap-4 lg:grid-cols-5">
            <Card className="flex flex-col gap-3 lg:col-span-3">
              <h2 className="text-base font-semibold text-fg">Outreach funnel</h2>
              {overview.emails_sent > 0 ? (
                <ComparisonBarChart data={funnelData} barKey="count" labelKey="label" />
              ) : (
                <p className="py-8 text-center text-sm text-fgMuted">
                  No emails sent yet — start a campaign to see delivery, opens, and replies here.
                </p>
              )}
              <div className="grid grid-cols-3 gap-3 border-t border-border pt-3 text-sm">
                <div>
                  <p className="text-fgMuted">Delivery rate</p>
                  <p className="font-mono font-semibold text-fg">{formatPercent(overview.delivery_rate)}</p>
                </div>
                <div>
                  <p className="text-fgMuted">Bounce rate</p>
                  <p className="font-mono font-semibold text-fg">{formatPercent(overview.bounce_rate)}</p>
                </div>
                <div>
                  <p className="text-fgMuted">Provider spend</p>
                  <p className="font-mono font-semibold text-fg">${overview.total_provider_cost.toFixed(2)}</p>
                </div>
              </div>
            </Card>

            <Card className="flex flex-col gap-3 lg:col-span-2">
              <h2 className="text-base font-semibold text-fg">Top sources</h2>
              {overview.top_sources.length > 0 ? (
                <ComparisonBarChart
                  data={overview.top_sources.map((s) => ({ provider: s.provider, count: s.count }))}
                  barKey="count"
                  labelKey="provider"
                  color="success"
                  height={Math.max(overview.top_sources.length * 32, 120)}
                />
              ) : (
                <p className="py-8 text-center text-sm text-fgMuted">No companies sourced yet.</p>
              )}
            </Card>
          </section>

          {overview.top_campaigns.length > 0 && (
            <section className="flex flex-col gap-3">
              <h2 className="text-base font-semibold text-fg">Top campaigns</h2>
              <Card className="flex flex-col divide-y divide-border p-0">
                {overview.top_campaigns.map((c) => (
                  <div key={c.campaign_id} className="flex items-center justify-between px-4 py-3 text-base">
                    <span className="font-medium text-fg">{c.name}</span>
                    <span className="font-mono text-sm tabular-nums text-fgMuted">
                      {c.sent} sent · {c.opened} opened · {c.replied} replied
                    </span>
                  </div>
                ))}
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
