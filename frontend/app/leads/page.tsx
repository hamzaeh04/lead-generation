"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronRight, FolderPlus, Search, Sparkles, Zap } from "lucide-react";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { CreateBatchDialog } from "@/components/leads/CreateBatchDialog";
import { GetLeadsDialog } from "@/components/leads/GetLeadsDialog";
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
  manual: { label: "Manual", badgeClass: "bg-emerald-600", icon: FolderPlus },
};

function formatBatchNumber(sequence: number): string {
  return `Batch ${String(sequence).padStart(2, "0")}`;
}

function batchTitle(batch: SearchBatch): string {
  return batch.name?.trim() || formatBatchNumber(batch.sequence);
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
          <p className="font-semibold text-fg">{batchTitle(batch)}</p>
          <p className="truncate text-sm text-fgMuted">
            {formatBatchNumber(batch.sequence)} · {info.label} · {date.toLocaleDateString()}{" "}
            {date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
          </p>
          {batch.description?.trim() && (
            <p className="mt-0.5 truncate text-xs text-fgSubtle">{batch.description}</p>
          )}
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-4">
        <span className="text-sm text-fgMuted">
          {totalLeads} lead{totalLeads === 1 ? "" : "s"}
        </span>
        <span className={cn("text-sm", batch.assigned_email ? "text-fgMuted" : "text-fgSubtle")}>
          {batch.assigned_email || "No email assigned"}
        </span>
        <ChevronRight className="h-4 w-4 text-fgSubtle" />
      </div>
    </Link>
  );
}

function LeadsContent({
  onRefresh,
}: {
  onRefresh: () => void;
}) {
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
          title="No batches yet"
          description="Create a batch to import CSV leads, or Get leads from Apollo / Smartlead."
          action={
            <div className="flex flex-wrap items-center justify-center gap-2">
              <CreateBatchDialog onCreated={() => onRefresh()} />
              <GetLeadsDialog onCreated={() => onRefresh()} />
            </div>
          }
        />
      )}

      {batches.length > 0 && (
        <Card interactive={false} className="flex flex-col divide-y divide-border p-0">
          {batches.map((batch) => (
            <BatchRow key={batch.id} batch={batch} />
          ))}
        </Card>
      )}
    </div>
  );
}

export default function LeadsPage() {
  const queryClient = useQueryClient();
  const { activeWorkspace } = useWorkspace();

  function refreshBatches() {
    queryClient.invalidateQueries({ queryKey: ["search-batches", activeWorkspace?.id] });
  }

  return (
    <AppShell
      title="Leads"
      description="Batches of leads — create one manually, import CSV, or discover via Apollo / Smartlead."
      actions={
        <div className="flex flex-wrap items-center gap-2">
          <CreateBatchDialog onCreated={() => refreshBatches()} />
          <GetLeadsDialog onCreated={() => refreshBatches()} />
        </div>
      }
    >
      <LeadsContent onRefresh={refreshBatches} />
    </AppShell>
  );
}
