"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronRight, Search, Sparkles, Zap } from "lucide-react";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { CardSkeleton } from "@/components/ui/Skeleton";
import { cn } from "@/lib/cn";
import { listSearchBatches, type SearchBatch } from "@/lib/api";
import { useWorkspace } from "@/lib/workspace-context";

const PROVIDER_INFO: Record<string, { label: string; badgeClass: string; icon: typeof Zap }> = {
  apollo: { label: "Apollo", badgeClass: "bg-indigo-500", icon: Zap },
  smartlead: {
    label: "Smartlead",
    badgeClass: "bg-gradient-to-br from-violet-500 to-pink-500",
    icon: Sparkles,
  },
};

function formatBatchNumber(sequence: number): string {
  return `Batch ${String(sequence).padStart(2, "0")}`;
}

function BatchRow({ batch }: { batch: SearchBatch }) {
  const info = PROVIDER_INFO[batch.provider] ?? {
    label: batch.provider,
    badgeClass: "bg-fgSubtle",
    icon: Zap,
  };
  const Icon = info.icon;
  const totalLeads = batch.contacts_created + batch.contacts_matched;
  const date = new Date(batch.created_at);

  return (
    <Link
      href={`/leads/batches/${batch.id}`}
      className="flex items-center justify-between gap-4 px-4 py-3.5 transition-colors hover:bg-surface2"
    >
      <div className="flex min-w-0 items-center gap-3">
        <span
          className={cn(
            "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-white",
            info.badgeClass
          )}
        >
          <Icon className="h-4 w-4" />
        </span>
        <div className="min-w-0">
          <p className="font-semibold text-fg">{formatBatchNumber(batch.sequence)}</p>
          <p className="truncate text-sm text-fgMuted">
            {info.label} · {date.toLocaleDateString()}{" "}
            {date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
          </p>
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-4">
        <span className="text-sm text-fgMuted">
          {totalLeads} lead{totalLeads === 1 ? "" : "s"}
        </span>
        <ChevronRight className="h-4 w-4 text-fgSubtle" />
      </div>
    </Link>
  );
}

function LeadsContent() {
  const { activeWorkspace } = useWorkspace();

  const batchesQuery = useQuery({
    queryKey: ["search-batches", activeWorkspace?.id],
    queryFn: () => listSearchBatches(activeWorkspace!.id, { limit: 100 }),
    enabled: !!activeWorkspace,
  });

  const batches = batchesQuery.data ?? [];

  return (
    <div className="flex flex-col gap-5">
      {batchesQuery.isLoading && (
        <div className="grid grid-cols-1 gap-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <CardSkeleton key={i} />
          ))}
        </div>
      )}

      {!batchesQuery.isLoading && batches.length === 0 && (
        <EmptyState
          icon={Search}
          title="No searches run yet"
          description="Run a search on Discover to build your first batch of leads."
          action={
            <Link href="/discover">
              <Button size="sm">Discover leads</Button>
            </Link>
          }
        />
      )}

      {batches.length > 0 && (
        <Card className="flex flex-col divide-y divide-border p-0">
          {batches.map((batch) => (
            <BatchRow key={batch.id} batch={batch} />
          ))}
        </Card>
      )}
    </div>
  );
}

export default function LeadsPage() {
  return (
    <AppShell title="Leads" description="Every search run from Discover, grouped as a batch of leads.">
      <LeadsContent />
    </AppShell>
  );
}
