"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, Sparkles } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { AppShell } from "@/components/AppShell";
import { tierTone } from "@/components/leads/lead-table-columns";
import { Breadcrumb } from "@/components/ui/Breadcrumb";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Pill } from "@/components/ui/Pill";
import { CardSkeleton, Skeleton } from "@/components/ui/Skeleton";
import { StatCard } from "@/components/ui/StatCard";
import { TagInput } from "@/components/ui/TagInput";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/Tabs";
import { getErrorMessage } from "@/lib/errors";
import {
  findDecisionMakers,
  getCompany,
  getIntentScore,
  listCompanySources,
  listLeads,
  type Contact,
} from "@/lib/api";
import { useWorkspace } from "@/lib/workspace-context";

const DEFAULT_TITLES = ["owner", "founder", "president", "ceo", "general manager"];

const statusTone: Record<string, "success" | "warning" | "danger" | "accent" | "muted"> = {
  won: "success",
  meeting: "success",
  interested: "accent",
  replied: "accent",
  bounced: "danger",
  unsubscribed: "danger",
  lost: "danger",
};

function ContactRow({ contact }: { contact: Contact }) {
  return (
    <Link href={`/leads/${contact.id}`} className="flex items-center justify-between gap-3 px-4 py-3 hover:bg-surface2">
      <div>
        <div className="text-base font-medium text-fg">{contact.full_name ?? contact.email ?? "Unnamed contact"}</div>
        <div className="text-sm text-fgMuted">{contact.job_title ?? contact.email ?? "—"}</div>
      </div>
      <div className="flex items-center gap-3">
        {contact.latest_qualification && (
          <span className="flex items-center gap-1.5" title="AI qualification">
            <Pill tone={tierTone[contact.latest_qualification.tier] ?? "muted"}>
              Tier {contact.latest_qualification.tier}
            </Pill>
            <span className="font-mono text-sm tabular-nums text-fgMuted">
              {Math.round(contact.latest_qualification.composite_score)}
            </span>
          </span>
        )}
        <Pill tone={statusTone[contact.status] ?? "muted"}>{contact.status.replace(/_/g, " ")}</Pill>
      </div>
    </Link>
  );
}

function fieldRow(label: string, value: React.ReactNode) {
  if (!value) return null;
  return (
    <div className="flex items-center justify-between border-b border-border py-2.5 text-base last:border-0">
      <span className="text-fgMuted">{label}</span>
      <span className="text-fg">{value}</span>
    </div>
  );
}

function CompanyDetailContent({ companyId }: { companyId: string }) {
  const { activeWorkspace } = useWorkspace();
  const workspaceId = activeWorkspace?.id;
  const queryClient = useQueryClient();
  const [titles, setTitles] = useState<string[]>(DEFAULT_TITLES);

  const companyQuery = useQuery({
    queryKey: ["company", workspaceId, companyId],
    queryFn: () => getCompany(workspaceId!, companyId),
    enabled: !!workspaceId,
  });

  const contactsQuery = useQuery({
    queryKey: ["company-contacts", workspaceId, companyId],
    queryFn: () => listLeads(workspaceId!, { company_id: companyId, limit: 100 }),
    enabled: !!workspaceId,
  });

  const sourcesQuery = useQuery({
    queryKey: ["company-sources", workspaceId, companyId],
    queryFn: () => listCompanySources(workspaceId!, companyId),
    enabled: !!workspaceId,
  });

  const intentQuery = useQuery({
    queryKey: ["company-intent", workspaceId, companyId],
    queryFn: () => getIntentScore(workspaceId!, companyId),
    enabled: !!workspaceId,
  });

  const decisionMakersMutation = useMutation({
    mutationFn: () => findDecisionMakers(workspaceId!, companyId, titles),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["company-contacts", workspaceId, companyId] });
      if (result.contacts.length === 0) {
        toast.info("Nobody found for these titles at this domain.");
      } else {
        toast.success(`${result.contacts_created} new, ${result.contacts_matched} already on file`);
      }
    },
    onError: (error) => toast.error(getErrorMessage(error, "Decision-maker search failed.")),
  });

  if (companyQuery.isLoading) {
    return (
      <div className="flex flex-col gap-6">
        <Skeleton className="h-6 w-64" />
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <CardSkeleton className="lg:col-span-2" />
          <CardSkeleton />
        </div>
      </div>
    );
  }

  if (companyQuery.isError || !companyQuery.data) {
    return <EmptyState title="Company not found" description="It may have been removed, or you may not have access." />;
  }

  const company = companyQuery.data;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Breadcrumb items={[{ label: "Companies", href: "/companies" }, { label: company.name ?? "Company" }]} />
        <h1 className="mt-2 text-2xl font-semibold tracking-tight text-fg">{company.name ?? "Unnamed company"}</h1>
        <p className="mt-1 text-sm text-fgMuted">
          {[company.industry, company.city, company.state].filter(Boolean).join(" · ") || "No profile details yet"}
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <StatCard
          label="Intent score"
          value={intentQuery.data ? `${intentQuery.data.score}/100` : <Skeleton className="h-8 w-16" />}
          hint={
            intentQuery.data
              ? `${intentQuery.data.signal_count} signal${intentQuery.data.signal_count === 1 ? "" : "s"} on file`
              : undefined
          }
        />
        <StatCard label="Contacts" value={contactsQuery.data?.length ?? <Skeleton className="h-8 w-10" />} />
      </div>

      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="contacts">
            Contacts{contactsQuery.data ? ` (${contactsQuery.data.length})` : ""}
          </TabsTrigger>
          <TabsTrigger value="signals">Signals</TabsTrigger>
          <TabsTrigger value="sources">Sources</TabsTrigger>
        </TabsList>

        <TabsContent value="overview">
          <Card>
            <h2 className="mb-1 text-base font-semibold text-fg">Profile</h2>
            <div className="flex flex-col">
              {fieldRow(
                "Website",
                company.website && (
                  <a href={company.website} target="_blank" rel="noreferrer" className="text-accent hover:underline">
                    {company.website}
                  </a>
                )
              )}
              {fieldRow("Domain", company.domain)}
              {fieldRow("Phone", company.phone)}
              {fieldRow(
                "Address",
                [company.address, company.city, company.state, company.country, company.postal_code]
                  .filter(Boolean)
                  .join(", ") || null
              )}
              {fieldRow("Employees", company.employee_count)}
              {fieldRow(
                "LinkedIn",
                company.linkedin_url && (
                  <a href={company.linkedin_url} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-accent hover:underline">
                    View profile <ExternalLink className="h-3 w-3" />
                  </a>
                )
              )}
              {fieldRow("First seen", new Date(company.first_seen).toLocaleDateString())}
              {fieldRow("Last seen", new Date(company.last_seen).toLocaleDateString())}
            </div>
            {company.description && (
              <p className="mt-3 border-t border-border pt-3 text-base leading-relaxed text-fgMuted">
                {company.description}
              </p>
            )}
          </Card>
        </TabsContent>

        <TabsContent value="contacts">
          <div className="flex flex-col gap-3">
            {company.domain ? (
              <Card className="flex flex-col gap-3">
                <div className="flex items-center gap-2 text-base font-semibold text-fg">
                  <Sparkles className="h-4 w-4 text-accent" />
                  Find decision-makers
                </div>
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                  <TagInput value={titles} onChange={setTitles} placeholder="owner, founder, ceo…" className="flex-1" />
                  <Button
                    variant="ghost"
                    loading={decisionMakersMutation.isPending}
                    onClick={() => decisionMakersMutation.mutate()}
                    className="shrink-0"
                  >
                    Search
                  </Button>
                </div>
              </Card>
            ) : (
              <p className="text-sm text-fgMuted">Add a domain to search for decision-makers.</p>
            )}

            {contactsQuery.data && contactsQuery.data.length > 0 ? (
              <Card className="flex flex-col divide-y divide-border p-0">
                {contactsQuery.data.map((contact) => (
                  <ContactRow key={contact.id} contact={contact} />
                ))}
              </Card>
            ) : (
              <EmptyState title="No contacts found at this company yet" />
            )}
          </div>
        </TabsContent>

        <TabsContent value="signals">
          {intentQuery.data && intentQuery.data.signals.length > 0 ? (
            <Card className="flex flex-col divide-y divide-border p-0">
              {intentQuery.data.signals.map((signal) => (
                <div key={signal.id} className="flex flex-col gap-1 px-4 py-3">
                  <div className="flex items-center justify-between">
                    <span className="text-base font-medium text-fg">{signal.signal_type.replace(/_/g, " ")}</span>
                    <span className="text-sm text-fgMuted">{new Date(signal.detected_at).toLocaleDateString()}</span>
                  </div>
                  {signal.signal_text && <p className="text-sm text-fgMuted">{signal.signal_text}</p>}
                  <a href={signal.source_url} target="_blank" rel="noreferrer" className="text-sm text-accent hover:underline">
                    Source
                  </a>
                </div>
              ))}
            </Card>
          ) : (
            <EmptyState title="No intent signals yet" />
          )}
        </TabsContent>

        <TabsContent value="sources">
          {sourcesQuery.data && sourcesQuery.data.length > 0 ? (
            <Card className="flex flex-col divide-y divide-border p-0">
              {sourcesQuery.data.map((source) => (
                <div key={source.id} className="flex items-center justify-between gap-3 px-4 py-3 text-base">
                  <span className="font-mono text-fg">{source.provider}</span>
                  <span className="text-fgMuted">{source.source_type}</span>
                  {source.source_url ? (
                    <a href={source.source_url} target="_blank" rel="noreferrer" className="text-accent hover:underline">
                      View source
                    </a>
                  ) : (
                    <span className="text-fgMuted">—</span>
                  )}
                  <span className="text-fgMuted">{new Date(source.retrieved_at).toLocaleDateString()}</span>
                </div>
              ))}
            </Card>
          ) : (
            <EmptyState title="No provenance records" description="This company has no recorded source yet." />
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

export default function CompanyDetailPage() {
  const params = useParams<{ id: string }>();
  return (
    <AppShell title="Company">
      <CompanyDetailContent companyId={params.id} />
    </AppShell>
  );
}
