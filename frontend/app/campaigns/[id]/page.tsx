"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, ChevronUp, Pencil, Plus, Trash2 } from "lucide-react";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
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
import { Checkbox } from "@/components/ui/Checkbox";
import { Combobox } from "@/components/ui/Combobox";
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
  deleteCampaignStep,
  enrollBatches,
  getCampaign,
  getCampaignReport,
  listEmailSetups,
  listLeads,
  listSearchBatches,
  pauseCampaign,
  previewCampaignStep,
  processCampaignNow,
  resumeCampaign,
  startCampaign,
  updateCampaignStep,
  type Campaign,
  type CampaignStatus,
  type CampaignStep,
  type SearchBatch,
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

const DEFAULT_SUBJECT = "{{first_name}}, quick question";
const DEFAULT_BODY = "Hi {{first_name}},\n\nI wanted to reach out about {{company_name}}.\n\nBest regards";

function StepsSection({
  campaign,
  workspaceId,
  subject,
  body,
  onSubjectChange,
  onBodyChange,
}: {
  campaign: Campaign;
  workspaceId: string;
  subject: string;
  body: string;
  onSubjectChange: (value: string) => void;
  onBodyChange: (value: string) => void;
}) {
  const queryClient = useQueryClient();
  const sortedSteps = useMemo(
    () => [...campaign.steps].sort((a, b) => a.step_number - b.step_number),
    [campaign.steps]
  );
  const nextStepNumber = Math.max(0, ...campaign.steps.map((s) => s.step_number)) + 1;
  const stepOne = sortedSteps.find((s) => s.step_number === 1) ?? sortedSteps[0] ?? null;

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (stepOne) {
        return updateCampaignStep(workspaceId, campaign.id, stepOne.id, {
          subject: subject.trim(),
          body: body.trim(),
        });
      }
      return addCampaignStep(workspaceId, campaign.id, {
        step_number: 1,
        delay_days: 0,
        subject: subject.trim(),
        body: body.trim(),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["campaign", workspaceId, campaign.id] });
      toast.success(stepOne ? "Email content saved" : "Step 1 created");
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  return (
    <Card className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h2 className="text-base font-semibold text-fg">Sequence steps</h2>
          <p className="mt-1 text-sm text-fgMuted">
            Subject and body below are sent with enroll — use {"{{first_name}}"} and{" "}
            {"{{company_name}}"} for personalization.
          </p>
        </div>
        {campaign.steps.length > 0 && (
          <AddStepDialog campaignId={campaign.id} workspaceId={workspaceId} nextStepNumber={nextStepNumber} />
        )}
      </div>

      <Field label="Subject" htmlFor="sequence_subject" hint="Included in the enroll payload and used for the first send.">
        <Input
          id="sequence_subject"
          required
          value={subject}
          onChange={(e) => onSubjectChange(e.target.value)}
          placeholder={DEFAULT_SUBJECT}
        />
      </Field>

      <Field label="Email body" htmlFor="sequence_body">
        <Textarea
          id="sequence_body"
          required
          rows={8}
          value={body}
          onChange={(e) => onBodyChange(e.target.value)}
          placeholder={DEFAULT_BODY}
        />
      </Field>

      <Button
        type="button"
        variant="ghost"
        className="self-start"
        loading={saveMutation.isPending}
        disabled={!subject.trim() || !body.trim()}
        onClick={() => saveMutation.mutate()}
      >
        Save email content
      </Button>

      {sortedSteps.length > 1 && (
        <div className="mt-2 flex flex-col divide-y divide-border border-t border-border pt-2">
          <p className="px-0 py-2 text-xs font-semibold uppercase tracking-wide text-fgSubtle">
            Follow-up steps
          </p>
          {sortedSteps
            .filter((step) => step.id !== stepOne?.id)
            .map((step, i, arr) => (
              <StepCard
                key={step.id}
                step={step}
                campaign={campaign}
                workspaceId={workspaceId}
                isFirst={false}
                isLast={i === arr.length - 1}
              />
            ))}
        </div>
      )}
    </Card>
  );
}

function batchLabel(batch: SearchBatch) {
  const seq = String(batch.sequence).padStart(2, "0");
  const contacts = batch.contacts_created + batch.contacts_matched;
  return `Batch ${seq} · ${batch.provider} · ${contacts} contact${contacts === 1 ? "" : "s"}`;
}

function SequenceTab({ campaign, workspaceId }: { campaign: Campaign; workspaceId: string }) {
  const stepOne =
    [...campaign.steps].sort((a, b) => a.step_number - b.step_number).find((s) => s.step_number === 1) ??
    campaign.steps[0] ??
    null;

  const [subject, setSubject] = useState(stepOne?.subject ?? DEFAULT_SUBJECT);
  const [body, setBody] = useState(stepOne?.body ?? DEFAULT_BODY);

  useEffect(() => {
    if (!stepOne) return;
    setSubject(stepOne.subject);
    setBody(stepOne.body);
  }, [stepOne?.id, stepOne?.subject, stepOne?.body]);

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <StepsSection
        campaign={campaign}
        workspaceId={workspaceId}
        subject={subject}
        body={body}
        onSubjectChange={setSubject}
        onBodyChange={setBody}
      />
      <EnrollSection
        campaignId={campaign.id}
        workspaceId={workspaceId}
        campaignFromEmail={campaign.from_email}
        subject={subject}
        body={body}
      />
    </div>
  );
}

function EnrollSection({
  campaignId,
  workspaceId,
  campaignFromEmail,
  subject,
  body,
}: {
  campaignId: string;
  workspaceId: string;
  campaignFromEmail: string;
  subject: string;
  body: string;
}) {
  const queryClient = useQueryClient();
  const [selectedBatchIds, setSelectedBatchIds] = useState<Set<string>>(new Set());
  const [emailSetupId, setEmailSetupId] = useState("");

  const batchesQuery = useQuery({
    queryKey: ["search-batches", workspaceId],
    queryFn: () => listSearchBatches(workspaceId, { limit: 100 }),
  });

  const setupsQuery = useQuery({
    queryKey: ["email-setups"],
    queryFn: () => listEmailSetups(),
  });

  const batches = batchesQuery.data ?? [];
  const setups = setupsQuery.data ?? [];
  const selectedCount = selectedBatchIds.size;
  const selectedSetup = setups.find((s) => s.id === emailSetupId) ?? null;
  const canSend = selectedCount > 0 && !!emailSetupId && !!subject.trim() && !!body.trim();

  useEffect(() => {
    if (emailSetupId || setups.length === 0) return;
    const preferred =
      setups.find((s) => s.smtp_email.toLowerCase() === campaignFromEmail.toLowerCase()) ??
      setups.find((s) => s.is_default) ??
      setups[0];
    if (preferred) setEmailSetupId(preferred.id);
  }, [setups, emailSetupId, campaignFromEmail]);

  function toggleBatch(batchId: string, checked: boolean) {
    setSelectedBatchIds((prev) => {
      const next = new Set(prev);
      if (checked) next.add(batchId);
      else next.delete(batchId);
      return next;
    });
  }

  function toggleAll(checked: boolean) {
    if (!checked) {
      setSelectedBatchIds(new Set());
      return;
    }
    setSelectedBatchIds(new Set(batches.map((b) => b.id)));
  }

  const mutation = useMutation({
    mutationFn: () =>
      enrollBatches(workspaceId, campaignId, Array.from(selectedBatchIds), emailSetupId, {
        subject: subject.trim(),
        body: body.trim(),
      }),
    onSuccess: (result) => {
      setSelectedBatchIds(new Set());
      queryClient.invalidateQueries({ queryKey: ["campaign", workspaceId, campaignId] });
      const sent = result.sent ?? 0;
      const failed = result.failed ?? 0;
      toast.success(
        `${result.enrolled} enrolled · ${sent} sent · ${failed} failed · ${result.already_enrolled} already enrolled`
      );
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  return (
    <Card className="flex flex-col gap-3">
      <div>
        <h2 className="text-base font-semibold text-fg">Enroll contacts</h2>
        <p className="mt-1 text-sm text-fgMuted">
          Pick an SMTP account and batches. Enroll sends the Sequence subject and body from this
          tab in the API payload.
        </p>
      </div>

      <Field
        label="Send from (Email Setup)"
        hint="SMTP account used for this enroll-and-send."
      >
        <Select
          value={emailSetupId || undefined}
          onValueChange={setEmailSetupId}
          disabled={setupsQuery.isLoading || setups.length === 0}
        >
          <SelectTrigger>
            <SelectValue
              placeholder={
                setupsQuery.isLoading
                  ? "Loading SMTP accounts…"
                  : setups.length === 0
                    ? "No Email Setup accounts — add one first"
                    : "Select SMTP email"
              }
            />
          </SelectTrigger>
          <SelectContent>
            {setups.map((setup) => (
              <SelectItem key={setup.id} value={setup.id}>
                {setup.name} — {setup.smtp_email}
                {setup.is_default ? " (default)" : ""}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Field>

      {selectedSetup && (
        <p className="text-xs text-fgMuted">
          Sending as <span className="font-medium text-fg">{selectedSetup.smtp_email}</span> via{" "}
          {selectedSetup.smtp_host}:{selectedSetup.smtp_port}
        </p>
      )}

      {(!subject.trim() || !body.trim()) && (
        <p className="text-sm text-warning">Add a subject and email body in Sequence steps first.</p>
      )}

      {batchesQuery.isLoading && (
        <div className="flex items-center gap-2 text-sm text-fgMuted">
          <Skeleton className="h-4 w-4 rounded" /> Loading batches…
        </div>
      )}

      {batchesQuery.isSuccess && batches.length === 0 && (
        <EmptyState
          title="No batches yet"
          description="Run a Discover search first — each run becomes a batch you can enroll here."
        />
      )}

      {batches.length > 0 && (
        <div className="flex flex-col gap-2 rounded-lg border border-border">
          <label className="flex items-center gap-2 border-b border-border px-3 py-2 text-sm font-medium text-fg">
            <Checkbox
              checked={selectedCount > 0 && selectedCount === batches.length}
              onCheckedChange={(value) => toggleAll(value === true)}
            />
            Select all batches
          </label>
          <ul className="max-h-80 divide-y divide-border overflow-y-auto">
            {batches.map((batch) => {
              const checked = selectedBatchIds.has(batch.id);
              return (
                <li key={batch.id}>
                  <label className="flex cursor-pointer items-start gap-3 px-3 py-2.5 hover:bg-surface2">
                    <Checkbox
                      checked={checked}
                      onCheckedChange={(value) => toggleBatch(batch.id, value === true)}
                      className="mt-0.5"
                    />
                    <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                      <span className="text-sm font-medium text-fg">{batchLabel(batch)}</span>
                      <span className="text-xs text-fgMuted">
                        {new Date(batch.created_at).toLocaleString()} · {batch.category.replace(/_/g, " ")}
                      </span>
                    </span>
                  </label>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      <Button
        disabled={!canSend}
        loading={mutation.isPending}
        onClick={() => mutation.mutate()}
        className="self-start"
      >
        Enroll {selectedCount || ""} batch{selectedCount === 1 ? "" : "es"} &amp; send
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
          <SequenceTab campaign={campaign} workspaceId={workspaceId} />
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
