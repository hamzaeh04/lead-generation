"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type RowSelectionState } from "@tanstack/react-table";
import { Download, Gauge, Mail, MailWarning, Phone, Sparkles, Users2, XCircle, Zap } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { AppShell } from "@/components/AppShell";
import { StartCampaignDialog } from "@/components/campaigns/StartCampaignDialog";
import { ImportLeadsCsvDialog } from "@/components/leads/ImportLeadsCsvDialog";
import { bulkTargetStatuses, leadColumns } from "@/components/leads/lead-table-columns";
import { Breadcrumb } from "@/components/ui/Breadcrumb";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { InlineEditableText } from "@/components/ui/InlineEditableText";
import { CardSkeleton } from "@/components/ui/Skeleton";
import { StatCard } from "@/components/ui/StatCard";
import {
  bulkUpdateLeadStatus,
  enrichPhonesBatch,
  exportLeadsCsv,
  getSearchBatch,
  qualifyBatch,
  renameSearchBatch,
  revealBatch,
  type LeadStatus,
} from "@/lib/api";
import { getErrorMessage } from "@/lib/errors";
import { useWorkspace } from "@/lib/workspace-context";

const PROVIDER_INFO: Record<string, { label: string; badgeClass: string; icon: typeof Zap }> = {
  apollo: { label: "Apollo", badgeClass: "bg-indigo-500", icon: Zap },
  smartlead: {
    label: "Smartlead",
    badgeClass: "bg-gradient-to-br from-violet-500 to-pink-500",
    icon: Sparkles,
  },
  manual: { label: "Manual", badgeClass: "bg-emerald-600", icon: Users2 },
};

function BatchDetailContent({ batchId }: { batchId: string }) {
  const { activeWorkspace } = useWorkspace();
  const workspaceId = activeWorkspace?.id;
  const queryClient = useQueryClient();
  const router = useRouter();
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({});
  // Apollo delivers phone numbers asynchronously via webhook, not in the
  // /enrich-phones response — poll for a bounded window after a click so
  // numbers appear without a manual refresh, same as scoring already
  // does. Bounded (unlike scoring, which stops once every lead has a
  // score) because a "miss" here is permanent — Apollo just doesn't have
  // that person's number — so polling would otherwise never stop.
  const [phoneEnrichRequestedAt, setPhoneEnrichRequestedAt] = useState<number | null>(null);

  const batchQuery = useQuery({
    queryKey: ["search-batch", workspaceId, batchId],
    queryFn: () => getSearchBatch(workspaceId!, batchId),
    enabled: !!workspaceId,
    // Scoring AND email reveal both run as background tasks after the
    // search response returns (see search_service.qualify_contacts_in_
    // background / reveal_contacts_in_background — reveal used to run
    // inline, but a full-size search's sequential per-contact Apollo/
    // Smartlead calls could take well over a minute, past ngrok/proxy
    // timeouts) — the leads on this page can go from masked/unscored to
    // revealed/scored with nobody clicking anything, so poll for that
    // instead of requiring a manual reload. Stops on its own once every
    // lead has settled, so it doesn't poll forever on an already-settled
    // batch.
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return false;
      const stillScoring = data.contacts.some((c) => c.latest_qualification === null);
      const stillOutreach = ["drafting", "sending"].includes(data.outreach_status);
      const ageMs = Date.now() - new Date(data.created_at).getTime();
      // New batches sit on "idle" until the background job starts — poll
      // for a short window so Delivery ticks appear without a refresh.
      const recentIdle = data.outreach_status === "idle" && ageMs < 10 * 60 * 1000;
      const pendingPhoneReveal =
        phoneEnrichRequestedAt !== null &&
        Date.now() - phoneEnrichRequestedAt < 2 * 60 * 1000 &&
        data.contacts.some((c) => c.phone_reveal_attempted && !c.phone);
      // Only Apollo/Smartlead auto-reveal email — a manually-created batch
      // never sets email_reveal_attempted, which would otherwise poll
      // forever.
      const stillRevealingEmail =
        (data.provider === "apollo" || data.provider === "smartlead") &&
        data.contacts.some((c) => !c.email_reveal_attempted);
      if (stillScoring || stillOutreach || recentIdle || pendingPhoneReveal || stillRevealingEmail) return 4000;
      return false;
    },
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

  // Scoring and email reveal both already run automatically right after a
  // search — these are manual recovery actions for when that background
  // work got interrupted (server restart mid-batch, network blip), not a
  // replacement for the automatic flow. Both skip anything already
  // scored/revealed, so re-running never re-spends a credit or AI call on
  // a lead that's already done.
  const qualifyMutation = useMutation({
    mutationFn: () => qualifyBatch(workspaceId!, batchId),
    onSuccess: (result) => {
      // Scoring runs in the background now (each lead genuinely takes
      // 30-40+ seconds, too long to hold this request open) — this only
      // confirms what got scheduled, not final results. The batch page
      // already polls every 4s, so scores appear on their own as they land.
      if (result.scheduled === 0) {
        toast.success("All leads in this batch are already scored");
      } else {
        toast.success(
          `Scoring ${result.scheduled} lead${result.scheduled === 1 ? "" : "s"} in the background — ` +
            "this can take a while, scores will appear here as they finish"
        );
      }
      queryClient.invalidateQueries({ queryKey: ["search-batch", workspaceId, batchId] });
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const revealMutation = useMutation({
    mutationFn: () => revealBatch(workspaceId!, batchId),
    onSuccess: (result) => {
      // Reveal runs in the background now (a real reveal is a live
      // Apollo/Smartlead API call per lead, too slow to hold the request
      // open for a full batch) — this only confirms what got scheduled,
      // not final results. The batch page already polls while any
      // contact hasn't had reveal attempted yet, so emails appear on
      // their own as they land.
      if (result.scheduled === 0) {
        toast.success("All leads in this batch are already revealed");
      } else {
        toast.success(
          `Enriching ${result.scheduled} lead${result.scheduled === 1 ? "" : "s"} in the background — ` +
            "emails will appear here as they finish"
        );
      }
      queryClient.invalidateQueries({ queryKey: ["search-batch", workspaceId, batchId] });
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  // Apollo only, and manual-only (never automatic) — phone reveal spends
  // extra Apollo credits on top of the email reveal that already runs
  // automatically. Apollo delivers the actual number asynchronously via
  // webhook, not in this response, so this only confirms what got
  // requested; numbers land on the page's existing polling/refresh.
  const enrichPhonesMutation = useMutation({
    mutationFn: () => enrichPhonesBatch(workspaceId!, batchId),
    onSuccess: (result) => {
      if (result.requested === 0) {
        toast.success("No leads need phone enrichment — already requested or missing");
      } else {
        setPhoneEnrichRequestedAt(Date.now());
        toast.success(
          `Requested phone numbers for ${result.requested} lead${result.requested === 1 ? "" : "s"} — ` +
            "Apollo delivers these shortly, this page will update on its own"
        );
      }
      queryClient.invalidateQueries({ queryKey: ["search-batch", workspaceId, batchId] });
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const exportMutation = useMutation({
    mutationFn: () => exportLeadsCsv(workspaceId!, batchId),
    onSuccess: (blob) => {
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      const sequence = batch?.sequence ?? 0;
      anchor.href = url;
      anchor.download = `batch_${String(sequence).padStart(2, "0")}_leads.csv`;
      anchor.click();
      URL.revokeObjectURL(url);
      toast.success("CSV downloaded");
    },
    onError: (error) => toast.error(getErrorMessage(error, "Export failed")),
  });

  const renameMutation = useMutation({
    mutationFn: (name: string) => renameSearchBatch(workspaceId!, batchId, name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["search-batch", workspaceId, batchId] });
      queryClient.invalidateQueries({ queryKey: ["search-batches", workspaceId] });
    },
    onError: (error) => toast.error(getErrorMessage(error, "Could not rename batch")),
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
  const scoredLeads = batch.contacts.filter((c) => c.latest_qualification !== null).length;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Breadcrumb
          items={[
            { label: "Leads", href: "/leads" },
            {
              label:
                batch.name?.trim() ||
                `Batch ${String(batch.sequence).padStart(2, "0")}`,
            },
          ]}
        />
        <div className="flex shrink-0 items-center gap-2">
          <ImportLeadsCsvDialog
            workspaceId={workspaceId!}
            batchId={batchId}
            onImported={() =>
              queryClient.invalidateQueries({ queryKey: ["search-batch", workspaceId, batchId] })
            }
          />
          <Button
            size="sm"
            variant="ghost"
            loading={exportMutation.isPending}
            onClick={() => exportMutation.mutate()}
            title="Download this batch's leads as CSV"
          >
            <Download className="h-3.5 w-3.5" />
            Export CSV
          </Button>
        </div>
      </div>

      <Card className="flex items-center gap-4">
        <span
          className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-white ${info.badgeClass}`}
        >
          <Icon className="h-5 w-5" />
        </span>
        <div className="min-w-0 flex-1">
          <InlineEditableText
            as="h2"
            className="inline-block text-lg font-semibold text-fg"
            value={batch.name?.trim() || `Batch ${String(batch.sequence).padStart(2, "0")}`}
            onSave={(next) => renameMutation.mutate(next)}
          />
          <p className="text-sm text-fgMuted">
            {batch.name?.trim()
              ? `Batch ${String(batch.sequence).padStart(2, "0")} · `
              : ""}
            Sourced via {info.label} · {date.toLocaleDateString()}{" "}
            {date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
          </p>
          {batch.description?.trim() && (
            <p className="mt-1 text-sm text-fgSubtle">{batch.description}</p>
          )}
        </div>
        <div className="flex min-w-0 flex-1 flex-wrap items-center justify-end gap-3">
          <span
            className="flex items-center gap-1.5 text-xs text-fgMuted"
            title="AI-scored leads out of total leads in this batch"
          >
            <Gauge className="h-3.5 w-3.5" />
            {scoredLeads}/{totalLeads} scored
          </span>
          <span
            className="rounded-md border border-border bg-surface2 px-2 py-1 text-xs capitalize text-fgMuted"
            title="Auto draft + send pipeline for this batch"
          >
            Outreach: {(batch.outreach_status ?? "idle").replace(/_/g, " ")}
          </span>
          <StartCampaignDialog
            workspaceId={workspaceId!}
            batchId={batchId}
            batchSequence={batch.sequence}
            onStarted={() =>
              queryClient.invalidateQueries({ queryKey: ["search-batch", workspaceId, batchId] })
            }
          />
          <Button
            size="sm"
            variant="ghost"
            loading={revealMutation.isPending}
            onClick={() => revealMutation.mutate()}
            title="Enrich any leads missing email/details — skips leads already enriched"
          >
            <Mail className="h-3.5 w-3.5" />
            Enrich emails
          </Button>
          {batch.provider === "apollo" && (
            <Button
              size="sm"
              variant="ghost"
              loading={enrichPhonesMutation.isPending}
              onClick={() => enrichPhonesMutation.mutate()}
              title="Request phone numbers from Apollo (extra credits) — delivered shortly after, not instantly"
            >
              <Phone className="h-3.5 w-3.5" />
              Enrich phones
            </Button>
          )}
          <Button
            size="sm"
            variant="ghost"
            loading={qualifyMutation.isPending}
            onClick={() => qualifyMutation.mutate()}
            title="Score any leads missing an AI qualification — skips leads already scored"
          >
            <Gauge className="h-3.5 w-3.5" />
            Score leads
          </Button>
        </div>
      </Card>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        <StatCard label="Total leads" value={totalLeads} icon={Users2} />
        <StatCard label="New contacts" value={batch.contacts_created} />
        <StatCard label="Already known" value={batch.contacts_matched} />
        <StatCard
          label="Bounce rate"
          value={batch.bounce_rate !== null ? `${Math.round(batch.bounce_rate * 100)}%` : "—"}
          hint={batch.emails_sent > 0 ? `${batch.bounced} of ${batch.emails_sent} sent` : "No emails sent yet"}
          icon={MailWarning}
          tone="danger"
        />
        <StatCard
          label="Rejection rate"
          value={batch.rejection_rate !== null ? `${Math.round(batch.rejection_rate * 100)}%` : "—"}
          hint={
            batch.emails_sent + batch.rejected > 0
              ? `${batch.rejected} of ${batch.emails_sent + batch.rejected} attempted`
              : "No sends attempted yet"
          }
          icon={XCircle}
          tone="danger"
        />
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
