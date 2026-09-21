"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Briefcase, Building2, ExternalLink, EyeOff, Mail, MapPin, Phone, Sparkles } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { AppShell } from "@/components/AppShell";
import { Breadcrumb } from "@/components/ui/Breadcrumb";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Checkbox } from "@/components/ui/Checkbox";
import { EmptyState } from "@/components/ui/EmptyState";
import { Input } from "@/components/ui/Input";
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
import {
  createLeadNote,
  createLeadTask,
  getLead,
  getLeadScore,
  listLeadNotes,
  listLeadPersonalizations,
  listLeadTasks,
  personalizeLead,
  revealLead,
  updateLeadStatus,
  updateLeadTask,
  type LeadStatus,
} from "@/lib/api";
import { getErrorMessage } from "@/lib/errors";
import { useWorkspace } from "@/lib/workspace-context";

const statusFlow: LeadStatus[] = [
  "new",
  "verified",
  "ready_for_outreach",
  "contacted",
  "opened",
  "clicked",
  "replied",
  "interested",
  "meeting",
  "won",
  "lost",
  "unsubscribed",
  "bounced",
];

function LeadDetailContent({ contactId }: { contactId: string }) {
  const { activeWorkspace } = useWorkspace();
  const workspaceId = activeWorkspace?.id;
  const queryClient = useQueryClient();
  const [noteText, setNoteText] = useState("");
  const [taskTitle, setTaskTitle] = useState("");

  const leadQuery = useQuery({
    queryKey: ["lead", workspaceId, contactId],
    queryFn: () => getLead(workspaceId!, contactId),
    enabled: !!workspaceId,
  });

  const leadScoreQuery = useQuery({
    queryKey: ["lead-score", workspaceId, contactId],
    queryFn: () => getLeadScore(workspaceId!, contactId),
    enabled: !!workspaceId,
  });

  const notesQuery = useQuery({
    queryKey: ["lead-notes", workspaceId, contactId],
    queryFn: () => listLeadNotes(workspaceId!, contactId),
    enabled: !!workspaceId,
  });

  const tasksQuery = useQuery({
    queryKey: ["lead-tasks", workspaceId, contactId],
    queryFn: () => listLeadTasks(workspaceId!, contactId),
    enabled: !!workspaceId,
  });

  const personalizationsQuery = useQuery({
    queryKey: ["lead-personalizations", workspaceId, contactId],
    queryFn: () => listLeadPersonalizations(workspaceId!, contactId),
    enabled: !!workspaceId,
  });

  const statusMutation = useMutation({
    mutationFn: (status: LeadStatus) => updateLeadStatus(workspaceId!, contactId, status),
    onSuccess: (contact) => {
      queryClient.setQueryData(["lead", workspaceId, contactId], contact);
      toast.success("Status updated");
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const personalizeMutation = useMutation({
    mutationFn: () => personalizeLead(workspaceId!, contactId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["lead-personalizations", workspaceId, contactId] });
      toast.success("Draft generated");
    },
    onError: (error) => toast.error(getErrorMessage(error, "Draft generation failed.")),
  });

  const revealMutation = useMutation({
    mutationFn: () => revealLead(workspaceId!, contactId),
    onSuccess: (result) => {
      queryClient.setQueryData(["lead", workspaceId, contactId], result.contact);
      toast[result.revealed ? "success" : "info"](
        result.revealed ? "Details revealed" : "Nothing new to reveal for this lead"
      );
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const noteMutation = useMutation({
    mutationFn: (text: string) => createLeadNote(workspaceId!, contactId, text),
    onSuccess: () => {
      setNoteText("");
      queryClient.invalidateQueries({ queryKey: ["lead-notes", workspaceId, contactId] });
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const taskMutation = useMutation({
    mutationFn: (title: string) => createLeadTask(workspaceId!, contactId, { title }),
    onSuccess: () => {
      setTaskTitle("");
      queryClient.invalidateQueries({ queryKey: ["lead-tasks", workspaceId, contactId] });
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const toggleTaskMutation = useMutation({
    mutationFn: ({ taskId, completed }: { taskId: string; completed: boolean }) =>
      updateLeadTask(workspaceId!, contactId, taskId, { completed }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["lead-tasks", workspaceId, contactId] }),
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  if (leadQuery.isLoading) {
    return (
      <div className="flex flex-col gap-6">
        <Skeleton className="h-6 w-64" />
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <CardSkeleton />
          <CardSkeleton />
        </div>
      </div>
    );
  }

  if (leadQuery.isError || !leadQuery.data) {
    return <EmptyState title="Lead not found" description="It may have been removed, or you may not have access." />;
  }

  const lead = leadQuery.data;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Breadcrumb items={[{ label: "Leads", href: "/leads" }, { label: lead.full_name ?? lead.email ?? "Contact" }]} />
        <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-fg">
              {lead.full_name ?? lead.email ?? "Unnamed contact"}
            </h1>
            <p className="mt-1 text-sm text-fgMuted">
              {lead.job_title ?? "—"}
              {lead.company_id && (
                <>
                  {" at "}
                  <Link href={`/companies/${lead.company_id}`} className="text-accent hover:underline">
                    {lead.company_name ?? "company"}
                  </Link>
                </>
              )}
            </p>
          </div>
          <Select
            value={lead.status}
            onValueChange={(v) => statusMutation.mutate(v as LeadStatus)}
            disabled={statusMutation.isPending}
          >
            <SelectTrigger className="w-[190px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {statusFlow.map((s) => (
                <SelectItem key={s} value={s}>
                  {s.replace(/_/g, " ")}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <StatCard
        label="Lead score"
        value={leadScoreQuery.data ? `${leadScoreQuery.data.score}/100` : <Skeleton className="h-8 w-16" />}
        hint={leadScoreQuery.data?.breakdown.join(" · ") || "Fit + intent + authority + reachability + engagement"}
      />

      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="activity">Activity</TabsTrigger>
        </TabsList>

        <TabsContent value="overview">
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Card className="flex flex-col gap-3">
              <h2 className="text-base font-semibold text-fg">Contact info</h2>
              <div className="flex flex-col gap-2.5 text-sm">
                <div className="flex items-center gap-2.5">
                  <Mail className="h-3.5 w-3.5 shrink-0 text-fgSubtle" />
                  {lead.email ? (
                    <span className="text-fg">{lead.email}</span>
                  ) : lead.revealable ? (
                    <>
                      <span className="text-fgMuted">Hidden</span>
                      <Button
                        variant="ghost"
                        size="sm"
                        loading={revealMutation.isPending}
                        onClick={() => revealMutation.mutate()}
                      >
                        <EyeOff className="h-3 w-3" />
                        Reveal
                      </Button>
                    </>
                  ) : (
                    <span className="text-fgMuted">—</span>
                  )}
                </div>
                <div className="flex items-center gap-2.5">
                  <Phone className="h-3.5 w-3.5 shrink-0 text-fgSubtle" />
                  <span className="text-fg">{lead.phone ?? "—"}</span>
                </div>
                <div className="flex items-center gap-2.5">
                  <ExternalLink className="h-3.5 w-3.5 shrink-0 text-fgSubtle" />
                  {lead.linkedin_url ? (
                    <a href={lead.linkedin_url} target="_blank" rel="noreferrer" className="text-accent hover:underline">
                      View profile
                    </a>
                  ) : (
                    <span className="text-fg">—</span>
                  )}
                </div>
              </div>
            </Card>

            {(lead.seniority || lead.department || lead.city || lead.state || lead.country || lead.industry || lead.sub_industry || lead.company_headcount || lead.company_revenue) && (
              <Card className="flex flex-col gap-3">
                <h2 className="text-base font-semibold text-fg">Firmographics</h2>
                <div className="flex flex-col gap-2.5 text-sm">
                  {(lead.seniority || lead.department) && (
                    <div className="flex items-center gap-2.5">
                      <Briefcase className="h-3.5 w-3.5 shrink-0 text-fgSubtle" />
                      <span className="text-fg">
                        {[lead.seniority, lead.department].filter(Boolean).join(" · ")}
                      </span>
                    </div>
                  )}
                  {(lead.city || lead.state || lead.country) && (
                    <div className="flex items-center gap-2.5">
                      <MapPin className="h-3.5 w-3.5 shrink-0 text-fgSubtle" />
                      <span className="text-fg">
                        {[lead.city, lead.state, lead.country].filter(Boolean).join(", ")}
                      </span>
                    </div>
                  )}
                  {(lead.industry || lead.sub_industry || lead.company_headcount || lead.company_revenue) && (
                    <div className="flex items-start gap-2.5">
                      <Building2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-fgSubtle" />
                      <span className="text-fg">
                        {[lead.industry, lead.sub_industry].filter(Boolean).join(" · ")}
                        {(lead.industry || lead.sub_industry) && (lead.company_headcount || lead.company_revenue) && (
                          <br />
                        )}
                        {[
                          lead.company_headcount ? `${lead.company_headcount} employees` : null,
                          lead.company_revenue ? `${lead.company_revenue} revenue` : null,
                        ]
                          .filter(Boolean)
                          .join(" · ")}
                      </span>
                    </div>
                  )}
                </div>
              </Card>
            )}

            <Card className="flex flex-col gap-3">
              <h2 className="flex items-center gap-2 text-base font-semibold text-fg">
                <Sparkles className="h-4 w-4 text-accent" />
                AI personalization
              </h2>
              <p className="text-sm text-fgMuted">
                Generates a grounded outreach draft from this contact&apos;s real data — never a fabricated fact.
              </p>
              <Button
                onClick={() => personalizeMutation.mutate()}
                loading={personalizeMutation.isPending}
                className="self-start"
              >
                Generate draft
              </Button>
              {personalizationsQuery.data && personalizationsQuery.data.length > 0 && (
                <div className="flex flex-col gap-3 border-t border-border pt-3">
                  {personalizationsQuery.data.slice(0, 1).map((gen) => (
                    <div key={gen.id} className="flex flex-col gap-1.5 text-sm">
                      {gen.subject && <p className="font-medium text-fg">{gen.subject}</p>}
                      {gen.body && <p className="whitespace-pre-wrap text-fgMuted">{gen.body}</p>}
                      <span className="text-xs text-fgSubtle">source: {gen.personalization_source ?? "generic"}</span>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="activity">
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="flex flex-col gap-3">
              <h2 className="text-base font-semibold text-fg">Notes</h2>
              <form
                className="flex gap-2"
                onSubmit={(e) => {
                  e.preventDefault();
                  if (noteText.trim()) noteMutation.mutate(noteText.trim());
                }}
              >
                <Input
                  value={noteText}
                  onChange={(e) => setNoteText(e.target.value)}
                  placeholder="Add a note…"
                  className="flex-1"
                />
                <Button type="submit" variant="ghost" loading={noteMutation.isPending}>
                  Add
                </Button>
              </form>
              {notesQuery.data && notesQuery.data.length > 0 ? (
                <Card className="flex flex-col divide-y divide-border p-0">
                  {notesQuery.data.map((note) => (
                    <div key={note.id} className="flex flex-col gap-1 px-4 py-3">
                      <p className="text-base text-fg">{note.text}</p>
                      <span className="text-xs text-fgSubtle">{new Date(note.created_at).toLocaleString()}</span>
                    </div>
                  ))}
                </Card>
              ) : (
                <EmptyState title="No notes yet" />
              )}
            </div>

            <div className="flex flex-col gap-3">
              <h2 className="text-base font-semibold text-fg">Tasks</h2>
              <form
                className="flex gap-2"
                onSubmit={(e) => {
                  e.preventDefault();
                  if (taskTitle.trim()) taskMutation.mutate(taskTitle.trim());
                }}
              >
                <Input
                  value={taskTitle}
                  onChange={(e) => setTaskTitle(e.target.value)}
                  placeholder="Add a task…"
                  className="flex-1"
                />
                <Button type="submit" variant="ghost" loading={taskMutation.isPending}>
                  Add
                </Button>
              </form>
              {tasksQuery.data && tasksQuery.data.length > 0 ? (
                <Card className="flex flex-col divide-y divide-border p-0">
                  {tasksQuery.data.map((task) => (
                    <label key={task.id} className="flex items-center gap-3 px-4 py-3">
                      <Checkbox
                        checked={task.completed}
                        onCheckedChange={(checked) =>
                          toggleTaskMutation.mutate({ taskId: task.id, completed: !!checked })
                        }
                      />
                      <span className={task.completed ? "text-base text-fgMuted line-through" : "text-base text-fg"}>
                        {task.title}
                      </span>
                    </label>
                  ))}
                </Card>
              ) : (
                <EmptyState title="No tasks yet" />
              )}
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}

export default function LeadDetailPage() {
  const params = useParams<{ id: string }>();
  return (
    <AppShell title="Lead">
      <LeadDetailContent contactId={params.id} />
    </AppShell>
  );
}
