"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Pill } from "@/components/ui/Pill";
import { Spinner } from "@/components/ui/Spinner";
import {
  addWorkspaceMember,
  getWorkspaceApiKeys,
  getWorkspaceApiKeysDefaults,
  listWorkspaceMembers,
  removeWorkspaceMember,
  updateWorkspace,
  updateWorkspaceMemberRole,
  upsertWorkspaceApiKeys,
  type WorkspaceApiKeysDefaults,
  type WorkspacePlan,
  type WorkspaceRole,
} from "@/lib/api";
import { useWorkspace } from "@/lib/workspace-context";

const inputClass =
  "rounded-lg border border-border bg-surface px-3 py-2 text-[13px] text-fg placeholder:text-fgMuted focus:border-accent focus:outline-none";

const roleOptions: WorkspaceRole[] = ["owner", "admin", "member", "viewer"];
const planOptions: WorkspacePlan[] = ["free", "starter", "professional", "agency", "enterprise"];

const roleTone: Record<WorkspaceRole, "success" | "accent" | "muted"> = {
  owner: "success",
  admin: "accent",
  member: "muted",
  viewer: "muted",
};

const FALLBACK_KEY_DEFAULTS: WorkspaceApiKeysDefaults = {
  apollo_api_key: "your-apollo-api-key",
  pdl_api_key: "your-pdl-api-key",
  serpapi_api_key: "your-serpapi-api-key",
  apify_api_token: "your-apify-api-token",
  phantombuster_api_key: "your-phantombuster-api-key",
  hunter_api_key: "your-hunter-api-key",
};

type ApiKeyField = keyof WorkspaceApiKeysDefaults;

const API_KEY_FIELDS: {
  key: ApiKeyField;
  label: string;
  envName: string;
  hasFlag:
    | "has_apollo_api_key"
    | "has_pdl_api_key"
    | "has_serpapi_api_key"
    | "has_apify_api_token"
    | "has_phantombuster_api_key"
    | "has_hunter_api_key";
  hint: string;
}[] = [
  {
    key: "apollo_api_key",
    label: "Apollo",
    envName: "APOLLO_API_KEY",
    hasFlag: "has_apollo_api_key",
    hint: "Company / person discovery via Apollo.",
  },
  {
    key: "pdl_api_key",
    label: "People Data Labs",
    envName: "PDL_API_KEY",
    hasFlag: "has_pdl_api_key",
    hint: "Person and company enrichment.",
  },
  {
    key: "serpapi_api_key",
    label: "SerpApi",
    envName: "SERPAPI_API_KEY",
    hasFlag: "has_serpapi_api_key",
    hint: "Google / Maps style discovery searches.",
  },
  {
    key: "apify_api_token",
    label: "Apify",
    envName: "APIFY_API_TOKEN",
    hasFlag: "has_apify_api_token",
    hint: "Actor-based scrapers and enrichers.",
  },
  {
    key: "phantombuster_api_key",
    label: "PhantomBuster",
    envName: "PHANTOMBUSTER_API_KEY",
    hasFlag: "has_phantombuster_api_key",
    hint: "LinkedIn / social automation phantoms.",
  },
  {
    key: "hunter_api_key",
    label: "Hunter",
    envName: "HUNTER_API_KEY",
    hasFlag: "has_hunter_api_key",
    hint: "Email discovery and verification.",
  },
];

function emptyKeyForm(): Record<ApiKeyField, string> {
  return {
    apollo_api_key: "",
    pdl_api_key: "",
    serpapi_api_key: "",
    apify_api_token: "",
    phantombuster_api_key: "",
    hunter_api_key: "",
  };
}

function ApiKeysSettingsCard({
  workspaceId,
  canEdit,
}: {
  workspaceId: string;
  canEdit: boolean;
}) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState(emptyKeyForm);
  const [savedFlash, setSavedFlash] = useState(false);

  const defaultsQuery = useQuery({
    queryKey: ["workspace-api-keys-defaults", workspaceId],
    queryFn: () => getWorkspaceApiKeysDefaults(workspaceId),
  });

  const keysQuery = useQuery({
    queryKey: ["workspace-api-keys", workspaceId],
    queryFn: () => getWorkspaceApiKeys(workspaceId),
  });

  const defaults = defaultsQuery.data ?? FALLBACK_KEY_DEFAULTS;
  const existing = keysQuery.data;
  const isCreate = !existing;

  useEffect(() => {
    setForm(emptyKeyForm());
  }, [workspaceId, existing?.id, existing?.updated_at]);

  const saveMutation = useMutation({
    mutationFn: () => {
      const payload: Partial<Record<ApiKeyField, string>> = {};
      for (const field of API_KEY_FIELDS) {
        const value = form[field.key].trim();
        if (value) payload[field.key] = value;
      }
      return upsertWorkspaceApiKeys(workspaceId, payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workspace-api-keys", workspaceId] });
      setForm(emptyKeyForm());
      setSavedFlash(true);
      window.setTimeout(() => setSavedFlash(false), 2000);
    },
  });

  return (
    <Card className="flex flex-col gap-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-[13px] font-semibold text-fg">Provider API keys</h2>
          <p className="mt-1 text-[12.5px] text-fgMuted">
            One set of credentials per workspace — save once to add, save again to update. Leave a
            field blank to keep the current key.
          </p>
        </div>
        {existing ? <Pill tone="accent">configured</Pill> : <Pill tone="muted">not set</Pill>}
      </div>

      {keysQuery.isLoading || defaultsQuery.isLoading ? (
        <div className="flex items-center gap-2 text-[13px] text-fgMuted">
          <Spinner /> Loading…
        </div>
      ) : (
        <form
          className="flex w-full flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (canEdit) saveMutation.mutate();
          }}
        >
          {API_KEY_FIELDS.map((field) => {
            const hasKey = existing?.[field.hasFlag] ?? false;
            return (
              <label key={field.key} className="flex w-full flex-col gap-1.5">
                <span className="flex items-center justify-between gap-2 text-[13px] font-medium text-fg">
                  <span>
                    {field.label}{" "}
                    <span className="font-normal text-fgMuted">({field.envName})</span>
                  </span>
                  {hasKey ? <Pill tone="success">set</Pill> : <Pill tone="muted">empty</Pill>}
                </span>
                <textarea
                  rows={3}
                  value={form[field.key]}
                  disabled={!canEdit || saveMutation.isPending}
                  onChange={(e) => setForm((prev) => ({ ...prev, [field.key]: e.target.value }))}
                  placeholder={hasKey ? "••••••••" : defaults[field.key]}
                  className={`${inputClass} w-full resize-y disabled:opacity-50`}
                  autoComplete="off"
                  spellCheck={false}
                />
                <span className="text-[11.5px] text-fgMuted">{field.hint}</span>
              </label>
            );
          })}

          <div className="flex flex-wrap items-center gap-2">
            {canEdit ? (
              <Button type="submit" disabled={saveMutation.isPending}>
                {saveMutation.isPending ? (
                  <Spinner className="h-3.5 w-3.5" />
                ) : isCreate ? (
                  "Add API keys"
                ) : (
                  "Update API keys"
                )}
              </Button>
            ) : (
              <p className="text-[12px] text-fgMuted">
                Only workspace owners and admins can edit API keys.
              </p>
            )}
            {savedFlash && <p className="text-[12.5px] text-success">Saved.</p>}
            {saveMutation.isError && (
              <p className="text-[12.5px] text-danger">Could not save API keys.</p>
            )}
          </div>
        </form>
      )}
    </Card>
  );
}

function WorkspaceSettingsContent() {
  const { activeWorkspace, currentUser } = useWorkspace();
  const workspaceId = activeWorkspace?.id;
  const queryClient = useQueryClient();
  const [memberEmail, setMemberEmail] = useState("");
  const [memberRole, setMemberRole] = useState<WorkspaceRole>("member");
  const [maxTeamMembers, setMaxTeamMembers] = useState<string>("");

  const membersQuery = useQuery({
    queryKey: ["workspace-members", workspaceId],
    queryFn: () => listWorkspaceMembers(workspaceId!),
    enabled: !!workspaceId,
  });

  const myRole = membersQuery.data?.find((m) => m.user_id === currentUser?.id)?.role;
  const isOwner = myRole === "owner";
  const isAdminOrOwner = myRole === "owner" || myRole === "admin";

  const planMutation = useMutation({
    mutationFn: (plan: WorkspacePlan) => updateWorkspace(workspaceId!, { plan }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["workspaces"] }),
  });

  const limitsMutation = useMutation({
    mutationFn: (max: number) => updateWorkspace(workspaceId!, { limits: { max_team_members: max } }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["workspaces"] }),
  });

  const addMemberMutation = useMutation({
    mutationFn: () => addWorkspaceMember(workspaceId!, memberEmail, memberRole),
    onSuccess: () => {
      setMemberEmail("");
      queryClient.invalidateQueries({ queryKey: ["workspace-members", workspaceId] });
    },
  });

  const roleMutation = useMutation({
    mutationFn: ({ memberId, role }: { memberId: string; role: WorkspaceRole }) =>
      updateWorkspaceMemberRole(workspaceId!, memberId, role),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["workspace-members", workspaceId] }),
  });

  const removeMutation = useMutation({
    mutationFn: (memberId: string) => removeWorkspaceMember(workspaceId!, memberId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["workspace-members", workspaceId] }),
  });

  if (!activeWorkspace || !workspaceId) {
    return <Spinner />;
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-[22px] font-semibold tracking-tight">Workspace settings</h1>
        <p className="mt-1 text-[13px] text-fgMuted">{activeWorkspace.name}</p>
      </div>

      <Card className="flex flex-col gap-4">
        <h2 className="text-[13px] font-semibold text-fg">Plan &amp; limits</h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <label className="flex flex-col gap-1.5 text-[12.5px] text-fgMuted">
            Plan
            <select
              value={activeWorkspace.plan}
              disabled={!isOwner || planMutation.isPending}
              onChange={(e) => planMutation.mutate(e.target.value as WorkspacePlan)}
              className={`${inputClass} disabled:opacity-50`}
            >
              {planOptions.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1.5 text-[12.5px] text-fgMuted">
            Max team members (blank = unlimited)
            <div className="flex gap-2">
              <input
                type="number"
                min={1}
                disabled={!isOwner}
                placeholder={String(activeWorkspace.limits.max_team_members ?? "unlimited")}
                value={maxTeamMembers}
                onChange={(e) => setMaxTeamMembers(e.target.value)}
                className={`${inputClass} flex-1 disabled:opacity-50`}
              />
              {isOwner && (
                <Button
                  variant="ghost"
                  disabled={!maxTeamMembers || limitsMutation.isPending}
                  onClick={() => limitsMutation.mutate(Number(maxTeamMembers))}
                >
                  Save
                </Button>
              )}
            </div>
          </label>
        </div>
        {!isOwner && (
          <p className="text-[12px] text-fgMuted">Only the workspace owner can change plan or limits.</p>
        )}
      </Card>

      <Card className="flex flex-col gap-4">
        <h2 className="text-[13px] font-semibold text-fg">Members</h2>

        {isAdminOrOwner && (
          <form
            className="flex flex-wrap gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (memberEmail.trim()) addMemberMutation.mutate();
            }}
          >
            <input
              type="email"
              required
              value={memberEmail}
              onChange={(e) => setMemberEmail(e.target.value)}
              placeholder="Existing user's email"
              className={`${inputClass} flex-1`}
            />
            <select
              value={memberRole}
              onChange={(e) => setMemberRole(e.target.value as WorkspaceRole)}
              className={inputClass}
            >
              {roleOptions
                .filter((r) => r !== "owner")
                .map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
            </select>
            <Button type="submit" disabled={addMemberMutation.isPending}>
              {addMemberMutation.isPending ? <Spinner className="h-3.5 w-3.5" /> : "Add"}
            </Button>
          </form>
        )}
        {addMemberMutation.isError && (
          <p className="text-[12.5px] text-danger">
            Could not add member — they must already have a registered account.
          </p>
        )}

        <div className="flex flex-col divide-y divide-border">
          {membersQuery.data?.map((member) => {
            const isOnlyOwner =
              member.role === "owner" && membersQuery.data!.filter((m) => m.role === "owner").length === 1;
            return (
              <div key={member.id} className="flex items-center justify-between gap-3 py-3 first:pt-0">
                <span className="text-[13px] text-fg">{member.email ?? member.user_id}</span>
                <div className="flex items-center gap-2">
                  {isOwner ? (
                    <select
                      value={member.role}
                      disabled={isOnlyOwner || roleMutation.isPending}
                      onChange={(e) =>
                        roleMutation.mutate({
                          memberId: member.id,
                          role: e.target.value as WorkspaceRole,
                        })
                      }
                      className={`${inputClass} py-1 text-[12px] disabled:opacity-50`}
                    >
                      {roleOptions.map((r) => (
                        <option key={r} value={r}>
                          {r}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <Pill tone={roleTone[member.role]}>{member.role}</Pill>
                  )}
                  {isAdminOrOwner && !isOnlyOwner && (
                    <Button
                      variant="ghost"
                      onClick={() => removeMutation.mutate(member.id)}
                      disabled={removeMutation.isPending}
                    >
                      Remove
                    </Button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </Card>

      <ApiKeysSettingsCard workspaceId={workspaceId} canEdit={isAdminOrOwner} />
    </div>
  );
}

export default function WorkspaceSettingsPage() {
  return (
    <AppShell title="Workspace settings">
      <WorkspaceSettingsContent />
    </AppShell>
  );
}
