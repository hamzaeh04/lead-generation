"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Megaphone } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import { Field } from "@/components/ui/Label";
import { Input } from "@/components/ui/Input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import { createCampaign, enrollBatches, listEmailSetups } from "@/lib/api";
import { getErrorMessage } from "@/lib/errors";

const FREQUENCY_OPTIONS = [5, 10, 15, 30, 45, 60] as const;

const AI_SUBJECT = "{{personalized_subject}}";
const AI_BODY = "{{personalized_body}}";

function detectLocalTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  } catch {
    return "UTC";
  }
}

/** Full IANA timezone list; falls back to a short set if the runtime lacks supportedValuesOf. */
function listTimezones(): string[] {
  try {
    const supported = (
      Intl as typeof Intl & { supportedValuesOf?: (key: string) => string[] }
    ).supportedValuesOf?.("timeZone");
    if (supported?.length) return [...supported].sort((a, b) => a.localeCompare(b));
  } catch {
    /* ignore */
  }
  return [
    "UTC",
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Los_Angeles",
    "Europe/London",
    "Europe/Paris",
    "Asia/Dubai",
    "Asia/Karachi",
    "Asia/Kolkata",
    "Asia/Shanghai",
    "Asia/Tokyo",
    "Australia/Sydney",
  ].sort((a, b) => a.localeCompare(b));
}

const TIMEZONE_OPTIONS = listTimezones();

export function StartCampaignDialog({
  workspaceId,
  batchId,
  batchSequence,
  onStarted,
}: {
  workspaceId: string;
  batchId: string;
  batchSequence: number;
  onStarted?: () => void;
}) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [fromName, setFromName] = useState("");
  const [emailSetupId, setEmailSetupId] = useState("");
  const [frequency, setFrequency] = useState<string>("5");
  const [windowStart, setWindowStart] = useState("09:00");
  const [windowEnd, setWindowEnd] = useState("19:00");
  const [timezone, setTimezone] = useState(() => {
    const local = detectLocalTimezone();
    return TIMEZONE_OPTIONS.includes(local) ? local : "UTC";
  });

  const setupsQuery = useQuery({
    queryKey: ["email-setups"],
    queryFn: () => listEmailSetups(),
    enabled: open,
  });

  const setups = setupsQuery.data ?? [];
  const selectedSetup = setups.find((s) => s.id === emailSetupId) ?? null;

  useEffect(() => {
    if (!open) return;
    setName((prev) => prev || `Batch ${String(batchSequence).padStart(2, "0")} campaign`);
  }, [open, batchSequence]);

  useEffect(() => {
    if (!open || emailSetupId || setups.length === 0) return;
    const preferred = setups.find((s) => s.is_default) ?? setups[0];
    if (preferred) setEmailSetupId(preferred.id);
  }, [open, setups, emailSetupId]);

  const mutation = useMutation({
    mutationFn: async () => {
      if (!selectedSetup) throw new Error("Select an SMTP email account first.");
      const interval = Number(frequency);
      const campaign = await createCampaign(workspaceId, {
        name: name.trim(),
        from_name: fromName || selectedSetup.name || undefined,
        from_email: selectedSetup.smtp_email,
        timezone,
        send_interval_minutes: interval,
        send_window_start: windowStart,
        send_window_end: windowEnd,
      });
      const enroll = await enrollBatches(workspaceId, campaign.id, [batchId], selectedSetup.id, {
        subject: AI_SUBJECT,
        body: AI_BODY,
        paced: true,
      });
      return { campaign, enroll };
    },
    onSuccess: ({ campaign, enroll }) => {
      queryClient.invalidateQueries({ queryKey: ["campaigns", workspaceId] });
      queryClient.invalidateQueries({ queryKey: ["search-batch", workspaceId, batchId] });
      setOpen(false);
      toast.success(
        `Campaign started · ${enroll.enrolled} enrolled` +
          (enroll.drafts_ready ? ` · ${enroll.drafts_ready} drafts ready` : "") +
          (enroll.drafts_generated ? ` (${enroll.drafts_generated} newly generated)` : "") +
          (enroll.sent ? ` · ${enroll.sent} sent now` : " · sends on schedule")
      );
      onStarted?.();
      // Keep name reset for next open
      setName(`Batch ${String(batchSequence).padStart(2, "0")} campaign`);
      setFromName("");
    },
    onError: (error) => toast.error(getErrorMessage(error, "Could not start campaign.")),
  });

  return (
    <>
      <Button size="sm" onClick={() => setOpen(true)}>
        <Megaphone className="h-3.5 w-3.5" />
        Start Campaign
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Start campaign</DialogTitle>
            <DialogDescription>
              Enrolls this batch and sends each lead&apos;s draft email on your schedule. Existing
              drafts are reused; missing drafts are generated automatically before send — one lead
              every selected interval, only inside your time window.
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
              if (!windowStart || !windowEnd) {
                toast.error("Set both start and end times for the sending window.");
                return;
              }
              mutation.mutate();
            }}
          >
            <div className="sm:col-span-2">
              <Field label="Campaign name" hint="Internal label — contacts never see this." htmlFor="sc_name">
                <Input
                  id="sc_name"
                  required
                  autoFocus
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Batch 03 outreach"
                />
              </Field>
            </div>

            <div className="sm:col-span-2">
              <Field label="SMTP email (Email Setup)" hint="Sender account used when this campaign sends mail.">
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

            <Field label="From name" hint='Optional — shown next to the from email.' htmlFor="sc_from_name">
              <Input
                id="sc_from_name"
                value={fromName}
                onChange={(e) => setFromName(e.target.value)}
                placeholder={selectedSetup?.name || "Your name"}
              />
            </Field>

            <div className="sm:col-span-2">
              <Field
                label="Email frequency"
                hint="One personalized email to one lead every selected interval."
              >
                <Select value={frequency} onValueChange={setFrequency}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select frequency" />
                  </SelectTrigger>
                  <SelectContent>
                    {FREQUENCY_OPTIONS.map((mins) => (
                      <SelectItem key={mins} value={String(mins)}>
                        {mins} minutes
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
            </div>

            <div className="sm:col-span-2 rounded-lg border border-border p-3">
              <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-fgSubtle">
                Sending time period
              </p>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <Field label="Time zone">
                  <Select value={timezone} onValueChange={setTimezone}>
                    <SelectTrigger id="sc_tz">
                      <SelectValue placeholder="Select time zone" />
                    </SelectTrigger>
                    <SelectContent className="max-h-64">
                      {TIMEZONE_OPTIONS.map((tz) => (
                        <SelectItem key={tz} value={tz}>
                          {tz.replace(/_/g, " ")}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </Field>
                <Field label="Start time" hint="e.g. 9:00 AM" htmlFor="sc_start">
                  <Input
                    id="sc_start"
                    type="time"
                    required
                    value={windowStart}
                    onChange={(e) => setWindowStart(e.target.value)}
                  />
                </Field>
                <Field label="End time" hint="e.g. 7:00 PM" htmlFor="sc_end">
                  <Input
                    id="sc_end"
                    type="time"
                    required
                    value={windowEnd}
                    onChange={(e) => setWindowEnd(e.target.value)}
                  />
                </Field>
              </div>
              <p className="mt-2 text-[12px] text-fgMuted">
                Emails send only between start and end in this time zone. Outside the window, the
                queue pauses and resumes at the next start time.
              </p>
            </div>

            <p className="sm:col-span-2 text-[12.5px] text-fgMuted">
              Each send uses that lead&apos;s saved draft (subject + body). If a lead has no draft
              yet, one is generated first, then emailed.
            </p>

            <DialogFooter className="sm:col-span-2">
              <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" loading={mutation.isPending} disabled={!selectedSetup}>
                Start campaign
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
