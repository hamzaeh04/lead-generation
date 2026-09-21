"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Clock, Gauge, Layers, Zap } from "lucide-react";
import { useMemo } from "react";
import { toast } from "sonner";
import { AppShell } from "@/components/AppShell";
import { Card } from "@/components/ui/Card";
import { Pill } from "@/components/ui/Pill";
import { CardSkeleton } from "@/components/ui/Skeleton";
import {
  getProviderHealth,
  listProviders,
  updateProviderConfig,
  type ProviderConfig,
  type ProviderHealth,
} from "@/lib/api";
import { getErrorMessage } from "@/lib/errors";
import { useWorkspace } from "@/lib/workspace-context";

function formatDuration(ms: number): string {
  return ms < 1000 ? `${Math.round(ms)}ms` : `${(ms / 1000).toFixed(1)}s`;
}

function Stat({ icon: Icon, label, value }: { icon: React.ComponentType<{ className?: string }>; label: string; value: string }) {
  return (
    <div className="flex items-center gap-1.5 text-xs text-fgMuted">
      <Icon className="h-3 w-3 shrink-0" />
      <span>
        {label}: <span className="font-mono font-medium text-fg">{value}</span>
      </span>
    </div>
  );
}

function ProviderCard({
  config,
  health,
  canEdit,
}: {
  config: ProviderConfig;
  health: ProviderHealth | undefined;
  canEdit: boolean;
}) {
  const queryClient = useQueryClient();

  const toggleMutation = useMutation({
    mutationFn: (enabled: boolean) => updateProviderConfig(config.id, { enabled }),
    onSuccess: (_, enabled) => {
      queryClient.invalidateQueries({ queryKey: ["providers"] });
      toast.success(`${config.provider} ${enabled ? "enabled" : "disabled"}`);
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const quota = health?.monthly_free_quota ?? config.monthly_free_quota;
  const remaining = health?.quota_remaining;

  return (
    <Card className="flex flex-col gap-3">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="font-mono text-base font-semibold text-fg">{config.provider}</p>
          <p className="text-xs text-fgMuted">{config.category.replace(/_/g, " ")}</p>
        </div>
        {canEdit ? (
          <button
            role="switch"
            aria-checked={config.enabled}
            disabled={toggleMutation.isPending}
            onClick={() => toggleMutation.mutate(!config.enabled)}
            className={`relative h-5 w-9 shrink-0 rounded-full transition-colors disabled:opacity-50 ${
              config.enabled ? "bg-accent" : "bg-surface2"
            }`}
          >
            <span
              className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow-card transition-transform ${
                config.enabled ? "translate-x-[18px]" : "translate-x-0.5"
              }`}
            />
          </button>
        ) : (
          <Pill tone={config.enabled ? "success" : "muted"}>{config.enabled ? "enabled" : "disabled"}</Pill>
        )}
      </div>

      <div className="grid grid-cols-2 gap-x-3 gap-y-1.5 border-t border-border pt-3">
        <Stat icon={Layers} label="Priority" value={String(config.priority)} />
        <Stat
          icon={Gauge}
          label="Quota"
          value={quota === null || quota === undefined ? "—" : remaining !== undefined ? `${remaining}/${quota}` : `${quota}/mo`}
        />
        <Stat icon={Zap} label="Success" value={health ? `${Math.round(health.success_rate * 100)}%` : "—"} />
        <Stat icon={Clock} label="Latency" value={health ? formatDuration(health.avg_duration_ms) : "—"} />
      </div>
      <p className="text-xs text-fgSubtle">
        Last success: {health?.last_success_at ? new Date(health.last_success_at).toLocaleDateString() : "never called"}
      </p>
    </Card>
  );
}

function ProvidersContent() {
  const { currentUser } = useWorkspace();

  const providersQuery = useQuery({ queryKey: ["providers"], queryFn: listProviders });
  const healthQuery = useQuery({ queryKey: ["providers-health"], queryFn: getProviderHealth });

  const healthByKey = useMemo(() => {
    const map = new Map<string, ProviderHealth>();
    for (const h of healthQuery.data ?? []) {
      map.set(`${h.provider}:${h.category}`, h);
    }
    return map;
  }, [healthQuery.data]);

  const canEdit = !!currentUser?.is_superuser;
  // Non-superusers can't act on anything, so only show what's actually
  // live for them. Superusers see every registry row — otherwise a
  // disabled-by-default provider (e.g. a newly wired-up one) could never
  // be turned on from this page.
  const providers = (providersQuery.data ?? []).filter((p) => canEdit || p.enabled);

  return (
    <div className="flex flex-col gap-6">
      {!canEdit && (
        <p className="text-sm text-fgMuted">Only a workspace admin&apos;s superuser account can enable/disable providers.</p>
      )}

      {providersQuery.isLoading && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <CardSkeleton key={i} />
          ))}
        </div>
      )}

      {providers.length > 0 && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {providers.map((config) => (
            <ProviderCard
              key={config.id}
              config={config}
              health={healthByKey.get(`${config.provider}:${config.category}`)}
              canEdit={canEdit}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default function ProvidersPage() {
  return (
    <AppShell title="Providers" description="The provider registry — every source discovery and outreach can draw from.">
      <ProvidersContent />
    </AppShell>
  );
}
