"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type RowSelectionState } from "@tanstack/react-table";
import { Sparkles, Users2, Zap } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { AppShell } from "@/components/AppShell";
import { bulkTargetStatuses, leadColumns } from "@/components/leads/lead-table-columns";
import { Breadcrumb } from "@/components/ui/Breadcrumb";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { CardSkeleton } from "@/components/ui/Skeleton";
import { StatCard } from "@/components/ui/StatCard";
import { bulkUpdateLeadStatus, getSearchBatch, type LeadStatus } from "@/lib/api";
import { getErrorMessage } from "@/lib/errors";
import { useWorkspace } from "@/lib/workspace-context";

const PROVIDER_INFO: Record<string, { label: string; badgeClass: string; icon: typeof Zap }> = {
  apollo: { label: "Apollo", badgeClass: "bg-indigo-500", icon: Zap },
  smartlead: {
    label: "Smartlead",
    badgeClass: "bg-gradient-to-br from-violet-500 to-pink-500",
    icon: Sparkles,
  },
};

function BatchDetailContent({ batchId }: { batchId: string }) {
  const { activeWorkspace } = useWorkspace();
  const workspaceId = activeWorkspace?.id;
  const queryClient = useQueryClient();
  const router = useRouter();
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({});

  const batchQuery = useQuery({
    queryKey: ["search-batch", workspaceId, batchId],
    queryFn: () => getSearchBatch(workspaceId!, batchId),
    enabled: !!workspaceId,
  });

  const batch = batchQuery.data;
  const selectedIds = Object.keys(rowSelection);

  const bulkMutation = useMutation({
    mutationFn: (targetStatus: LeadStatus) =>
      bulkUpdateLeadStatus(workspaceId!, selectedIds, targetStatus),
    onSuccess: (result) => {
      toast.success(`Updated ${result.updated} lead${result.updated === 1 ? "" : "s"}`);
      setRowSelection({});
      queryClient.invalidateQueries({ queryKey: ["search-batch", workspaceId, batchId] });
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  if (batchQuery.isLoading || !batch) {
    return (
      <div className="flex flex-col gap-4">
        <CardSkeleton className="h-20" />
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <CardSkeleton key={i} />
          ))}
        </div>
      </div>
    );
  }

  const info = PROVIDER_INFO[batch.provider] ?? {
    label: batch.provider,
    badgeClass: "bg-fgSubtle",
    icon: Zap,
  };
  const Icon = info.icon;
  const date = new Date(batch.created_at);
  const totalLeads = batch.contacts_created + batch.contacts_matched;

  return (
    <div className="flex flex-col gap-6">
      <Breadcrumb items={[{ label: "Leads", href: "/leads" }, { label: `Batch ${String(batch.sequence).padStart(2, "0")}` }]} />

      <Card className="flex items-center gap-4">
        <span
          className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-white ${info.badgeClass}`}
        >
          <Icon className="h-5 w-5" />
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="text-lg font-semibold text-fg">
            Batch {String(batch.sequence).padStart(2, "0")}
          </h2>
          <p className="text-sm text-fgMuted">
            Sourced via {info.label} · {date.toLocaleDateString()}{" "}
            {date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
          </p>
        </div>
      </Card>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label="Total leads" value={totalLeads} icon={Users2} />
        <StatCard label="New contacts" value={batch.contacts_created} />
        <StatCard label="Already known" value={batch.contacts_matched} />
        <StatCard label="Companies touched" value={batch.companies_created + batch.companies_matched} />
      </div>

      <DataTable
        columns={leadColumns}
        data={batch.contacts}
        getRowId={(row) => row.id}
        onRowClick={(row) => router.push(`/leads/${row.id}`)}
        emptyTitle="No leads in this batch"
        selectable
        rowSelection={rowSelection}
        onRowSelectionChange={setRowSelection}
        toolbar={
          <>
            {bulkTargetStatuses.map((s) => (
              <Button
                key={s}
                size="sm"
                variant="ghost"
                loading={bulkMutation.isPending && bulkMutation.variables === s}
                onClick={() => bulkMutation.mutate(s)}
              >
                Mark {s.replace(/_/g, " ")}
              </Button>
            ))}
          </>
        }
      />
    </div>
  );
}

export default function BatchDetailPage() {
  const params = useParams<{ batchId: string }>();

  return (
    <AppShell title="Lead batch" description="The leads this search run found.">
      <BatchDetailContent batchId={params.batchId} />
    </AppShell>
  );
}
