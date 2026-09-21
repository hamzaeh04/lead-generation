"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ColumnDef, type RowSelectionState } from "@tanstack/react-table";
import { ChevronDown, ChevronUp, Pencil, Plus, Trash2 } from "lucide-react";
import { useParams } from "next/navigation";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { AppShell } from "@/components/AppShell";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/AlertDialog";
import { Breadcrumb } from "@/components/ui/Breadcrumb";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Combobox } from "@/components/ui/Combobox";
import { DataTable } from "@/components/ui/DataTable";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import { EmptyState } from "@/components/ui/EmptyState";
import { Field } from "@/components/ui/Label";
import { Input } from "@/components/ui/Input";
import { Pill } from "@/components/ui/Pill";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import { CardSkeleton, Skeleton } from "@/components/ui/Skeleton";
import { StatCard } from "@/components/ui/StatCard";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/Tabs";
import { Textarea } from "@/components/ui/Textarea";
import { getErrorMessage } from "@/lib/errors";
import {
  addCampaignStep,
  cancelCampaign,
  type Contact,
  deleteCampaignStep,
  enrollContacts,
  getCampaign,
  getCampaignReport,
  listLeads,
  pauseCampaign,
  previewCampaignStep,
  processCampaignNow,
  resumeCampaign,
  startCampaign,
  updateCampaignStep,
  type Campaign,
  type CampaignStatus,
  type CampaignStep,
} from "@/lib/api";
import { useWorkspace } from "@/lib/workspace-context";

const statusTone: Record<CampaignStatus, "success" | "warning" | "danger" | "accent" | "muted"> = {
  running: "success",
  scheduled: "accent",
  paused: "warning",
  draft: "muted",
  completed: "success",
  cancelled: "danger",
};

// A step form's local draft shape, shared by the add-step and edit-step dialogs.
interface StepDraft {
  delay_days: number;
  subject: string;
  body: string;
}

const EMPTY_DRAFT: StepDraft = { delay_days: 0, subject: "", body: "" };

function StepFormFields({ draft, onChange }: { draft: StepDraft; onChange: (draft: StepDraft) => void }) {
  return (
    <div className="flex flex-col gap-4">
      <Field label="Delay (days after previous step)" htmlFor="delay_days">
        <Input
          id="delay_days"
          type="number"
          min={0}
          value={draft.delay_days}
          onChange={(e) => onChange({ ...draft, delay_days: Number(e.target.value) })}
        />
      </Field>
      <Field label="Subject" htmlFor="subject">
        <Input
          id="subject"
          required
          value={draft.subject}
          onChange={(e) => onChange({ ...draft, subject: e.target.value })}
          placeholder="{{first_name}}, quick question"
        />
      </Field>
      <Field label="Body" htmlFor="body">
        <Textarea
          id="body"
          required
          rows={6}
          value={draft.body}
          onChange={(e) => onChange({ ...draft, body: e.target.value })}
          placeholder={"Hi {{first_name}},\n\n…"}
        />
      </Field>
    </div>
  );
}

function LifecycleActions({ campaign, workspaceId }: { campaign: Campaign; workspaceId: string }) {
  const queryClient = useQueryClient();
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["campaign", workspaceId, campaign.id] });
  const onError = (error: unknown) => toast.error(getErrorMessage(error));

  const startMutation = useMutation({ mutationFn: () => startCampaign(workspaceId, campaign.id), onSuccess: invalidate, onError });
  const pauseMutation = useMutation({ mutationFn: () => pauseCampaign(workspaceId, campaign.id), onSuccess: invalidate, onError });
  const resumeMutation = useMutation({ mutationFn: () => resumeCampaign(workspaceId, campaign.id), onSuccess: invalidate, onError });
  const cancelMutation = useMutation({
    mutationFn: () => cancelCampaign(workspaceId, campaign.id),
    onSuccess: () => {
      invalidate();
      toast.success("Campaign cancelled");
    },
    onError,
  });

  const pending =
    startMutation.isPending || pauseMutation.isPending || resumeMutation.isPending || cancelMutation.isPending;
  const terminal = campaign.status === "completed" || campaign.status === "cancelled";

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Pill tone={statusTone[campaign.status]}>{campaign.status}</Pill>
      {(campaign.status === "draft" || campaign.status === "scheduled") && (
        <Button variant="ghost" disabled={pending || campaign.steps.length === 0} onClick={() => startMutation.mutate()}>
          Start
        </Button>
      )}
      {campaign.status === "running" && (
        <Button variant="ghost" disabled={pending} onClick={() => pauseMutation.mutate()}>
          Pause
        </Button>
      )}
      {campaign.status === "paused" && (
        <Button variant="ghost" disabled={pending} onClick={() => resumeMutation.mutate()}>
          Resume
        </Button>
      )}
      {!terminal && (
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button variant="danger" disabled={pending}>
              Cancel
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Cancel this campaign?</AlertDialogTitle>
              <AlertDialogDescription>
                This stops all future sends for every enrolled contact. This can&apos;t be undone.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Keep campaign</AlertDialogCancel>
              <AlertDialogAction onClick={() => cancelMutation.mutate()}>Cancel campaign</AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      )}
      {campaign.status === "draft" && campaign.steps.length === 0 && (
        <span className="text-sm text-fgMuted">Add at least one step before starting.</span>
      )}
    </div>
  );
}

function AddStepDialog({
  campaignId,
  workspaceId,
  nextStepNumber,
}: {
  campaignId: string;
  workspaceId: string;
  nextStepNumber: number;
}) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<StepDraft>(EMPTY_DRAFT);

  const mutation = useMutation({
    mutationFn: () =>
      addCampaignStep(workspaceId, campaignId, {
        step_number: nextStepNumber,
        delay_days: draft.delay_days,
        subject: draft.subject,
        body: draft.body,
      }),
    onSuccess: () => {
      setOpen(false);
      setDraft(EMPTY_DRAFT);
      queryClient.invalidateQueries({ queryKey: ["campaign", workspaceId, campaignId] });
      toast.success(`Step ${nextStepNumber} added`);
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <Button variant="ghost" onClick={() => setOpen(true)}>
        <Plus className="h-3.5 w-3.5" />
        Add step
      </Button>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add step {nextStepNumber}</DialogTitle>
          <DialogDescription>Use {"{{first_name}}"}, {"{{company_name}}"}, and other variables — see Preview to check them.</DialogDescription>
        </DialogHeader>
        <form
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            mutation.mutate();
          }}
        >
          <StepFormFields draft={draft} onChange={setDraft} />
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" loading={mutation.isPending}>
              Add step
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function EditStepDialog({
  step,
  campaignId,
  workspaceId,
  open,
  onOpenChange,
}: {
  step: CampaignStep;
  campaignId: string;
  workspaceId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<StepDraft>({
    delay_days: step.delay_days,
    subject: step.subject,
    body: step.body,
  });

  const mutation = useMutation({
    mutationFn: () => updateCampaignStep(workspaceId, campaignId, step.id, draft),
    onSuccess: () => {
      onOpenChange(false);
      queryClient.invalidateQueries({ queryKey: ["campaign", workspaceId, campaignId] });
      toast.success(`Step ${step.step_number} updated`);
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit step {step.step_number}</DialogTitle>
        </DialogHeader>
        <form
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            mutation.mutate();
          }}
        >
          <StepFormFields draft={draft} onChange={setDraft} />
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" loading={mutation.isPending}>
              Save changes
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function StepCard({
  step,
  campaign,
  workspaceId,
  isFirst,
  isLast,
}: {
  step: CampaignStep;
  campaign: Campaign;
  workspaceId: string;
  isFirst: boolean;
  isLast: boolean;
}) {
  const queryClient = useQueryClient();
  const [editOpen, setEditOpen] = useState(false);
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["campaign", workspaceId, campaign.id] });

  const deleteMutation = useMutation({
    mutationFn: () => deleteCampaignStep(workspaceId, campaign.id, step.id),
    onSuccess: () => {
      invalidate();
      toast.success(`Step ${step.step_number} deleted`);
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  // Swapping step_number with a neighbor: stage the moving step through a
  // temporary out-of-range number so the two PATCHes never collide with an
  // existing step_number mid-flight (the API 409s on a live collision).
  const moveMutation = useMutation({
    mutationFn: async (direction: "up" | "down") => {
      const sorted = [...campaign.steps].sort((a, b) => a.step_number - b.step_number);
      const index = sorted.findIndex((s) => s.id === step.id);
      const neighbor = sorted[direction === "up" ? index - 1 : index + 1];
      if (!neighbor) return;
      await updateCampaignStep(workspaceId, campaign.id, step.id, { step_number: 9999 });
      await updateCampaignStep(workspaceId, campaign.id, neighbor.id, { step_number: step.step_number });
      await updateCampaignStep(workspaceId, campaign.id, step.id, { step_number: neighbor.step_number });
    },
    onSuccess: invalidate,
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  return (
    <div className="flex flex-col gap-2 py-3 first:pt-0">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accentSoft text-xs font-semibold text-accent">
            {step.step_number}
          </span>
          <span className="text-base font-medium text-fg">
            {step.delay_days === 0 ? "Immediately" : `+${step.delay_days}d after previous`}
          </span>
          {!step.active && <Pill tone="muted">inactive</Pill>}
        </div>
        <div className="flex items-center gap-1">
          <button
            disabled={isFirst || moveMutation.isPending}
            onClick={() => moveMutation.mutate("up")}
            className="flex h-6 w-6 items-center justify-center rounded-md text-fgMuted hover:bg-surface2 disabled:cursor-not-allowed disabled:opacity-30"
            aria-label="Move step up"
          >
            <ChevronUp className="h-3.5 w-3.5" />
          </button>
          <button
            disabled={isLast || moveMutation.isPending}
            onClick={() => moveMutation.mutate("down")}
            className="flex h-6 w-6 items-center justify-center rounded-md text-fgMuted hover:bg-surface2 disabled:cursor-not-allowed disabled:opacity-30"
            aria-label="Move step down"
          >
            <ChevronDown className="h-3.5 w-3.5" />
          </button>
          <button
            onClick={() => setEditOpen(true)}
            className="flex h-6 w-6 items-center justify-center rounded-md text-fgMuted hover:bg-surface2"
            aria-label="Edit step"
          >
            <Pencil className="h-3.5 w-3.5" />
          </button>
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <button
                className="flex h-6 w-6 items-center justify-center rounded-md text-fgMuted hover:bg-dangerSoft hover:text-danger"
                aria-label="Delete step"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Delete step {step.step_number}?</AlertDialogTitle>
                <AlertDialogDescription>This removes it from the sequence permanently.</AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Keep step</AlertDialogCancel>
                <AlertDialogAction onClick={() => deleteMutation.mutate()}>Delete</AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </div>
      <p className="text-base text-fg">{step.subject}</p>
      <p className="line-clamp-2 whitespace-pre-wrap text-sm text-fgMuted">{step.body}</p>
      <EditStepDialog step={step} campaignId={campaign.id} workspaceId={workspaceId} open={editOpen} onOpenChange={setEditOpen} />
    </div>
  );
}

function StepsSection({ campaign, workspaceId }: { campaign: Campaign; workspaceId: string }) {
  const sortedSteps = useMemo(() => [...campaign.steps].sort((a, b) => a.step_number - b.step_number), [campaign.steps]);
  const nextStepNumber = campaign.steps.length + 1;

  return (
    <Card className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-fg">Sequence steps</h2>
        <AddStepDialog campaignId={campaign.id} workspaceId={workspaceId} nextStepNumber={nextStepNumber} />
      </div>
      {sortedSteps.length > 0 ? (
        <div className="flex flex-col divide-y divide-border">
          {sortedSteps.map((step, i) => (
            <StepCard
              key={step.id}
              step={step}
              campaign={campaign}
              workspaceId={workspaceId}
              isFirst={i === 0}
              isLast={i === sortedSteps.length - 1}
            />
          ))}
        </div>
      ) : (
        <p className="text-sm text-fgMuted">No steps yet.</p>
      )}
    </Card>
  );
}

const enrollColumns: ColumnDef<Contact, unknown>[] = [
  {
    accessorKey: "full_name",
    header: "Name",
    cell: ({ row }) => <span className="font-medium text-fg">{row.original.full_name ?? row.original.email ?? "Unnamed"}</span>,
  },
  {
    accessorKey: "email",
    header: "Email",
    cell: ({ row }) => <span className="text-fgMuted">{row.original.email ?? "no email"}</span>,
  },
  {
    accessorKey: "company_name",
    header: "Company",
    cell: ({ row }) => <span className="text-fgMuted">{row.original.company_name ?? "—"}</span>,
  },
];

function EnrollSection({ campaignId, workspaceId }: { campaignId: string; workspaceId: string }) {
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({});

  const leadsQuery = useQuery({
    queryKey: ["enroll-leads", workspaceId, query],
    queryFn: () => listLeads(workspaceId, { search: query || undefined, limit: 50 }),
  });

  const selectedIds = Object.keys(rowSelection);

  const mutation = useMutation({
    mutationFn: () => enrollContacts(workspaceId, campaignId, selectedIds),
    onSuccess: (result) => {
      setRowSelection({});
      toast.success(`${result.enrolled} enrolled, ${result.already_enrolled} already enrolled, ${result.not_found} not found`);
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  return (
    <Card className="flex flex-col gap-3">
      <h2 className="text-base font-semibold text-fg">Enroll contacts</h2>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          setQuery(search);
        }}
      >
        <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search leads to enroll…" />
      </form>

      <DataTable
        columns={enrollColumns}
        data={leadsQuery.data ?? []}
        getRowId={(row) => row.id}
        isLoading={leadsQuery.isLoading}
        selectable
        rowSelection={rowSelection}
        onRowSelectionChange={setRowSelection}
        emptyTitle="No leads match this search"
      />

      <Button disabled={selectedIds.length === 0} loading={mutation.isPending} onClick={() => mutation.mutate()} className="self-start">
        Enroll {selectedIds.length || ""}
      </Button>
    </Card>
  );
}

function PreviewSection({ campaign, workspaceId }: { campaign: Campaign; workspaceId: string }) {
  const [contactId, setContactId] = useState("");
  const [stepNumber, setStepNumber] = useState(campaign.steps[0]?.step_number ?? 1);
  const [search, setSearch] = useState("");

  const leadsQuery = useQuery({
    queryKey: ["preview-leads", workspaceId, search],
    queryFn: () => listLeads(workspaceId, { search: search || undefined, limit: 20 }),
  });

  const mutation = useMutation({
    mutationFn: () => previewCampaignStep(workspaceId, campaign.id, contactId, stepNumber),
    onError: (error) => toast.error(getErrorMessage(error, "Preview failed.")),
  });

  if (campaign.steps.length === 0) {
    return <EmptyState title="Add a step first" description="Preview needs at least one sequence step to render." />;
  }

  return (
    <Card className="flex flex-col gap-4">
      <h2 className="text-base font-semibold text-fg">Preview</h2>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <Field label="Step">
          <Select value={String(stepNumber)} onValueChange={(v) => setStepNumber(Number(v))}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {campaign.steps.map((s) => (
                <SelectItem key={s.id} value={String(s.step_number)}>
                  Step {s.step_number}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
        <Field label="Contact">
          <Combobox
            value={contactId}
            onChange={setContactId}
            placeholder="Search a contact…"
            searchPlaceholder="Type a name or email…"
            options={(leadsQuery.data ?? []).map((l) => ({
              value: l.id,
              label: l.full_name ?? l.email ?? "Unnamed",
              description: l.email ?? undefined,
            }))}
          />
        </Field>
      </div>
      <Button variant="ghost" disabled={!contactId} loading={mutation.isPending} onClick={() => mutation.mutate()} className="self-start">
        Render preview
      </Button>
      {mutation.data && (
        <div className="flex flex-col gap-2 rounded-lg border border-border p-3">
          <p className="text-base font-medium text-fg">{mutation.data.subject}</p>
          <p className="whitespace-pre-wrap text-sm text-fgMuted">{mutation.data.body}</p>
          {mutation.data.unrecognized_variables.length > 0 && (
            <p className="text-xs text-warning">Unrecognized variables: {mutation.data.unrecognized_variables.join(", ")}</p>
          )}
        </div>
      )}
    </Card>
  );
}

function formatPercent(value: number | null): string {
  return value === null ? "—" : `${Math.round(value * 1000) / 10}%`;
}

function ReportSection({ campaignId, workspaceId }: { campaignId: string; workspaceId: string }) {
  const reportQuery = useQuery({
    queryKey: ["campaign-report", workspaceId, campaignId],
    queryFn: () => getCampaignReport(workspaceId, campaignId),
  });

  const processMutation = useMutation({
    mutationFn: () => processCampaignNow(workspaceId, campaignId),
    onSuccess: (result) => {
      reportQuery.refetch();
      toast.success(`${result.sent} sent${result.skipped_no_quota ? " — daily limit reached" : ""}`);
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  if (!reportQuery.data) {
    return (
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <CardSkeleton />
        <CardSkeleton />
        <CardSkeleton />
      </div>
    );
  }

  const r = reportQuery.data;

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard label="Delivery rate" value={formatPercent(r.delivery_rate)} hint={`${r.delivered} delivered · ${r.bounced} bounced`} />
        <StatCard label="Open rate" value={formatPercent(r.open_rate)} hint={`${r.opened} opened · ${r.clicked} clicked`} />
        <StatCard
          label="Reply rate"
          value={formatPercent(r.reply_rate)}
          hint={`${r.replied} total · ${r.positive_replies} positive`}
        />
      </div>

      <Card className="flex flex-col gap-3">
        <h2 className="text-base font-semibold text-fg">Other stats</h2>
        <div className="grid grid-cols-3 gap-4 sm:grid-cols-5">
          {[
            ["Enrolled", r.contacts_enrolled],
            ["Sent", r.sent],
            ["Unsubscribed", r.unsubscribed],
            ["Meetings", r.meetings],
            ["Won", r.won],
          ].map(([label, value]) => (
            <div key={label} className="flex flex-col gap-1">
              <span className="text-2xs font-semibold uppercase tracking-wide text-fgSubtle">{label}</span>
              <span className="font-mono text-xl font-semibold tabular-nums text-fg">{value}</span>
            </div>
          ))}
        </div>
        <div className="border-t border-border pt-3">
          <Button variant="ghost" loading={processMutation.isPending} onClick={() => processMutation.mutate()}>
            Process due sends now
          </Button>
        </div>
      </Card>
    </div>
  );
}

function CampaignDetailContent({ campaignId }: { campaignId: string }) {
  const { activeWorkspace } = useWorkspace();
  const workspaceId = activeWorkspace?.id;

  const campaignQuery = useQuery({
    queryKey: ["campaign", workspaceId, campaignId],
    queryFn: () => getCampaign(workspaceId!, campaignId),
    enabled: !!workspaceId,
  });

  if (campaignQuery.isLoading) {
    return (
      <div className="flex flex-col gap-6">
        <Skeleton className="h-6 w-64" />
        <CardSkeleton />
      </div>
    );
  }

  if (campaignQuery.isError || !campaignQuery.data || !workspaceId) {
    return <EmptyState title="Campaign not found" />;
  }

  const campaign = campaignQuery.data;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Breadcrumb items={[{ label: "Campaigns", href: "/campaigns" }, { label: campaign.name }]} />
        <h1 className="mt-2 text-2xl font-semibold tracking-tight text-fg">{campaign.name}</h1>
        <p className="mt-1 text-sm text-fgMuted">
          {campaign.from_name ? `${campaign.from_name} <${campaign.from_email}>` : campaign.from_email} · {campaign.daily_limit}/day
        </p>
        <div className="mt-3">
          <LifecycleActions campaign={campaign} workspaceId={workspaceId} />
        </div>
      </div>

      <Tabs defaultValue="sequence">
        <TabsList>
          <TabsTrigger value="sequence">Sequence</TabsTrigger>
          <TabsTrigger value="preview">Preview</TabsTrigger>
          <TabsTrigger value="report">Report</TabsTrigger>
        </TabsList>

        <TabsContent value="sequence">
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <StepsSection campaign={campaign} workspaceId={workspaceId} />
            <EnrollSection campaignId={campaign.id} workspaceId={workspaceId} />
          </div>
        </TabsContent>

        <TabsContent value="preview">
          <PreviewSection campaign={campaign} workspaceId={workspaceId} />
        </TabsContent>

        <TabsContent value="report">
          <ReportSection campaignId={campaign.id} workspaceId={workspaceId} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

export default function CampaignDetailPage() {
  const params = useParams<{ id: string }>();
  return (
    <AppShell title="Campaign">
      <CampaignDetailContent campaignId={params.id} />
    </AppShell>
  );
}
