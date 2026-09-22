"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { AppShell } from "@/components/AppShell";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
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
import { TableSkeleton } from "@/components/ui/Skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import { createCampaign, listCampaigns, listEmailSetups, type CampaignStatus } from "@/lib/api";
import { getErrorMessage } from "@/lib/errors";
import { useWorkspace } from "@/lib/workspace-context";

const statusTone: Record<CampaignStatus, "success" | "warning" | "danger" | "accent" | "muted"> = {
  running: "success",
  scheduled: "accent",
  paused: "warning",
  draft: "muted",
  completed: "success",
  cancelled: "danger",
};

function CreateCampaignDialog({ onCreated }: { onCreated: (id: string) => void }) {
  const { activeWorkspace } = useWorkspace();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [fromName, setFromName] = useState("");
  const [emailSetupId, setEmailSetupId] = useState("");
  const [dailyLimit, setDailyLimit] = useState(50);

  const setupsQuery = useQuery({
    queryKey: ["email-setups"],
    queryFn: () => listEmailSetups(),
    enabled: open,
  });

  const setups = setupsQuery.data ?? [];
  const selectedSetup = setups.find((s) => s.id === emailSetupId) ?? null;

  useEffect(() => {
    if (!open || emailSetupId || setups.length === 0) return;
    const preferred = setups.find((s) => s.is_default) ?? setups[0];
    if (preferred) setEmailSetupId(preferred.id);
  }, [open, setups, emailSetupId]);

  const mutation = useMutation({
    mutationFn: () =>
      createCampaign(activeWorkspace!.id, {
        name,
        from_name: fromName || selectedSetup?.name || undefined,
        from_email: selectedSetup!.smtp_email,
        daily_limit: dailyLimit,
      }),
    onSuccess: (campaign) => {
      queryClient.invalidateQueries({ queryKey: ["campaigns", activeWorkspace?.id] });
      setOpen(false);
      setName("");
      setFromName("");
      setEmailSetupId("");
      setDailyLimit(50);
      onCreated(campaign.id);
    },
    onError: (error) => toast.error(getErrorMessage(error, "Could not create campaign.")),
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <Button onClick={() => setOpen(true)}>
        <Plus className="h-3.5 w-3.5" />
        New campaign
      </Button>
      <DialogContent className="max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Set up a new campaign</DialogTitle>
          <DialogDescription>
            Pick an SMTP account from Email Setup for sending, then name the campaign. You&apos;ll
            write the emails and enroll batches on the next page.
          </DialogDescription>
        </DialogHeader>
        <form
          className="grid grid-cols-1 gap-4 sm:grid-cols-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (!selectedSetup) {
              toast.error("Select an SMTP email account first.");
              return;
            }
            mutation.mutate();
          }}
        >
          <div className="sm:col-span-2">
            <Field label="Campaign name" hint="An internal label for you — contacts never see this." htmlFor="campaign_name">
              <Input
                id="campaign_name"
                required
                autoFocus
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Austin Dentists Q1"
              />
            </Field>
          </div>

          <div className="sm:col-span-2">
            <Field
              label="SMTP email (Email Setup)"
              hint="Sender account used when this campaign sends mail."
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
          </div>

          {selectedSetup && (
            <div className="sm:col-span-2 rounded-lg border border-border bg-surface2/40 p-3">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-fgSubtle">
                Selected SMTP details
              </p>
              <dl className="grid grid-cols-1 gap-2 text-sm sm:grid-cols-2">
                <div>
                  <dt className="text-fgMuted">name</dt>
                  <dd className="font-medium text-fg">{selectedSetup.name}</dd>
                </div>
                <div>
                  <dt className="text-fgMuted">smtp_email</dt>
                  <dd className="font-medium text-fg">{selectedSetup.smtp_email}</dd>
                </div>
                <div>
                  <dt className="text-fgMuted">smtp_host</dt>
                  <dd className="font-medium text-fg">{selectedSetup.smtp_host}</dd>
                </div>
                <div>
                  <dt className="text-fgMuted">smtp_port</dt>
                  <dd className="font-medium text-fg">{selectedSetup.smtp_port}</dd>
                </div>
                <div>
                  <dt className="text-fgMuted">smtp_use_tls</dt>
                  <dd className="font-medium text-fg">{selectedSetup.smtp_use_tls ? "true" : "false"}</dd>
                </div>
                <div>
                  <dt className="text-fgMuted">is_default</dt>
                  <dd className="font-medium text-fg">{selectedSetup.is_default ? "true" : "false"}</dd>
                </div>
              </dl>
            </div>
          )}

          <Field label="From name" hint='Optional — shown next to the from email, e.g. "Alex from Acme".' htmlFor="from_name">
            <Input
              id="from_name"
              value={fromName}
              onChange={(e) => setFromName(e.target.value)}
              placeholder={selectedSetup?.name || "Your name"}
            />
          </Field>
          <Field
            label="Daily send limit"
            hint="Max emails sent per day, so you don't blast everyone at once and get flagged as spam."
            htmlFor="daily_limit"
          >
            <Input
              id="daily_limit"
              type="number"
              min={1}
              value={dailyLimit}
              onChange={(e) => setDailyLimit(Number(e.target.value))}
            />
          </Field>
          <DialogFooter className="sm:col-span-2">
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" loading={mutation.isPending} disabled={!selectedSetup}>
              Create campaign
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function CampaignsContent() {
  const { activeWorkspace } = useWorkspace();
  const router = useRouter();

  const campaignsQuery = useQuery({
    queryKey: ["campaigns", activeWorkspace?.id],
    queryFn: () => listCampaigns(activeWorkspace!.id),
    enabled: !!activeWorkspace,
  });

  const campaigns = campaignsQuery.data ?? [];

  return (
    <div className="flex flex-col gap-6">
      {campaignsQuery.isLoading && <TableSkeleton cols={3} rows={4} />}

      {campaignsQuery.isSuccess && campaigns.length === 0 && (
        <EmptyState
          title="No campaigns yet"
          description="A campaign is an email sequence you send to a list of your leads — write the emails, pick who gets them, and track opens/replies as they come in."
          action={<CreateCampaignDialog onCreated={(id) => router.push(`/campaigns/${id}`)} />}
        />
      )}

      {campaigns.length > 0 && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {campaigns.map((campaign) => (
            <Link key={campaign.id} href={`/campaigns/${campaign.id}`}>
              <Card className="flex h-full flex-col gap-3 transition-colors hover:border-accent">
                <div className="flex items-start justify-between gap-2">
                  <span className="text-md font-medium text-fg">{campaign.name}</span>
                  <Pill tone={statusTone[campaign.status]}>{campaign.status}</Pill>
                </div>
                <div className="flex flex-col gap-1 text-sm text-fgMuted">
                  <span>{campaign.from_email}</span>
                  <span>
                    {campaign.steps.length} step{campaign.steps.length === 1 ? "" : "s"}
                  </span>
                  <span>{campaign.daily_limit}/day limit</span>
                </div>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

export default function CampaignsPage() {
  const router = useRouter();
  return (
    <AppShell
      title="Campaigns"
      description="Automated email sequences sent to your leads, with delivery/open/reply tracking."
      actions={<CreateCampaignDialog onCreated={(id) => router.push(`/campaigns/${id}`)} />}
    >
      <CampaignsContent />
    </AppShell>
  );
}
