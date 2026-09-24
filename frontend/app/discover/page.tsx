"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { Check, Search, Sparkles, Zap } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";
import { AppShell } from "@/components/AppShell";
import { ProspectPanel } from "@/components/discover/ProspectPanel";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Spinner } from "@/components/ui/Spinner";
import { StatCard } from "@/components/ui/StatCard";
import { cn } from "@/lib/cn";
import { type Contact, type DiscoveryCriteria, executeSearch, listProviders } from "@/lib/api";
import { getErrorMessage } from "@/lib/errors";
import { useWorkspace } from "@/lib/workspace-context";

const PROVIDER_INFO: Record<string, { label: string; description: string; badgeClass: string; icon: typeof Zap }> = {
  // apollo: {
  //   label: "Apollo",
  //   description: "270M+ verified people — AI prompt or structured filters",
  //   badgeClass: "bg-indigo-500",
  //   icon: Zap,
  // },
  smartlead: {
    label: "Smartlead SmartProspect",
    description: "AI-powered prospect finder — 270M+ verified profiles, or import from a campaign",
    badgeClass: "bg-gradient-to-br from-violet-500 to-pink-500",
    icon: Sparkles,
  },
};

function ProviderCard({
  providerName,
  active,
  onClick,
}: {
  providerName: string;
  active: boolean;
  onClick: () => void;
}) {
  const info = PROVIDER_INFO[providerName] ?? {
    label: providerName,
    description: "",
    badgeClass: "bg-fgSubtle",
    icon: Zap,
  };
  const Icon = info.icon;

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex items-start gap-3 rounded-xl border p-4 text-left shadow-card transition-all",
        active
          ? "border-accent bg-accentSoft"
          : "border-border bg-surface hover:-translate-y-0.5 hover:border-accent/50 hover:shadow-popover"
      )}
    >
      <span className={cn("flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-white", info.badgeClass)}>
        <Icon className="h-4 w-4" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex items-center gap-1.5">
          <span className="text-md font-semibold text-fg">{info.label}</span>
          {active && <Check className="h-3.5 w-3.5 shrink-0 text-accent" />}
        </span>
        <span className="mt-0.5 block text-sm text-fgMuted">{info.description}</span>
      </span>
    </button>
  );
}

function ContactResultRow({ contact }: { contact: Contact }) {
  return (
    <div className="flex items-center justify-between px-4 py-3">
      <Link href={`/leads/${contact.id}`} className="min-w-0 flex-1 hover:text-accent">
        <span className="block truncate text-base font-medium text-fg">
          {contact.full_name ?? contact.email ?? "Unnamed contact"}
        </span>
        <span className="block truncate text-sm text-fgMuted">
          {contact.job_title ?? "—"}
          {contact.company_name ? ` at ${contact.company_name}` : ""}
          {contact.city || contact.state
            ? ` · ${[contact.city, contact.state].filter(Boolean).join(", ")}`
            : ""}
        </span>
      </Link>
      <span className="ml-3 shrink-0 text-sm text-fgMuted">{contact.email ?? "—"}</span>
    </div>
  );
}

function DiscoverContent() {
  const { activeWorkspace } = useWorkspace();
  const workspaceId = activeWorkspace?.id;

  const [provider, setProvider] = useState("");
  const [criteria, setCriteria] = useState<DiscoveryCriteria>({ limit: 25 });

  const providersQuery = useQuery({ queryKey: ["providers"], queryFn: listProviders });

  const availableProviders = (providersQuery.data ?? []).filter(
    (p) =>
      p.enabled &&
      p.category === "person_discovery" &&
      // Apollo hidden on Discover for now — Smartlead only.
      p.provider !== "apollo"
  );
  const selectedProvider = provider || availableProviders[0]?.provider || "";

  const searchMutation = useMutation({
    mutationFn: (searchCriteria: DiscoveryCriteria) =>
      executeSearch({
        workspace_id: workspaceId!,
        provider: selectedProvider,
        category: "person_discovery",
        criteria: searchCriteria,
      }),
    onError: (error) => toast.error(getErrorMessage(error, "Search failed — the provider may be unavailable.")),
  });

  const results = searchMutation.data;
  const hasResults = results && (results.companies.length > 0 || results.contacts.length > 0);

  return (
    <div className="flex flex-col gap-5">
      <div>
        <p className="mb-2 text-sm font-medium text-fgMuted">Data source</p>
        {providersQuery.isSuccess && availableProviders.length === 0 ? (
          <p className="text-sm text-danger">
            No lead-prospecting provider is enabled. Ask a workspace admin to enable Smartlead on the
            Providers page.
          </p>
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {availableProviders.map((p) => (
              <ProviderCard
                key={p.id}
                providerName={p.provider}
                active={selectedProvider === p.provider}
                onClick={() => {
                  setProvider(p.provider);
                  setCriteria({ limit: 25 });
                }}
              />
            ))}
          </div>
        )}
      </div>

      <div className="flex flex-col gap-6">
        <Card className="flex w-full flex-col gap-4">
          {selectedProvider === "smartlead" ? (
            <ProspectPanel
              provider={selectedProvider}
              workspaceId={workspaceId}
              criteria={criteria}
              onCriteriaChange={setCriteria}
              onSearch={(searchCriteria) => searchMutation.mutate(searchCriteria)}
              searching={searchMutation.isPending}
            />
          ) : (
            <p className="text-sm text-fgMuted">Choose a data source above to start searching.</p>
          )}

          {searchMutation.isError && (
            <p className="text-sm text-danger">
              {getErrorMessage(searchMutation.error, "Search failed — the provider may be unavailable.")}
            </p>
          )}
        </Card>

        <div className="flex flex-col gap-4">
          {searchMutation.isPending && (
            <div className="flex items-center gap-2 text-sm text-fgMuted">
              <Spinner className="h-3.5 w-3.5" /> Searching…
            </div>
          )}

          {results && (
            <>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <StatCard label="Companies created" value={results.companies_created} />
                <StatCard label="Companies matched" value={results.companies_matched} />
                <StatCard label="Contacts created" value={results.contacts_created} />
                <StatCard label="Contacts matched" value={results.contacts_matched} />
              </div>
              {results.batch_id && (
                <Link href={`/leads/batches/${results.batch_id}`} className="self-start">
                  <Button variant="outline" size="sm">
                    View in Leads
                  </Button>
                </Link>
              )}

              {results.companies.length > 0 && (
                <div className="flex flex-col gap-2">
                  <h3 className="text-sm font-semibold text-fgMuted">Companies (found via these contacts)</h3>
                  <Card className="flex flex-col divide-y divide-border p-0">
                    {results.companies.map((company) => (
                      <Link
                        key={company.id}
                        href={`/companies/${company.id}`}
                        className="flex items-center justify-between px-4 py-3 hover:bg-surface2"
                      >
                        <span className="text-base font-medium text-fg">{company.name ?? "Unnamed company"}</span>
                        <span className="text-sm text-fgMuted">{company.domain ?? company.city ?? "—"}</span>
                      </Link>
                    ))}
                  </Card>
                </div>
              )}

              {results.contacts.length > 0 && (
                <div className="flex flex-col gap-2">
                  <h3 className="text-sm font-semibold text-fgMuted">Contacts</h3>
                  <Card className="flex flex-col divide-y divide-border p-0">
                    {results.contacts.map((contact) => (
                      <ContactResultRow key={contact.id} contact={contact} />
                    ))}
                  </Card>
                </div>
              )}

              {!hasResults && (
                <EmptyState title="Nothing found" description="The provider ran successfully but found nothing for these criteria." />
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default function DiscoverPage() {
  return (
    <AppShell
      title="Discover"
      description="Find real leads with Smartlead — AI prompt or manual filters."
      fullWidth
    >
      <DiscoverContent />
    </AppShell>
  );
}
