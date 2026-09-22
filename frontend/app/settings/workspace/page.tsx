"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { AppShell } from "@/components/AppShell";
import { SettingsNav } from "@/components/SettingsNav";
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
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
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
import { Skeleton } from "@/components/ui/Skeleton";
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
import { getErrorMessage } from "@/lib/errors";
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
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workspaces"] });
      toast.success("Plan updated");
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const limitsMutation = useMutation({
    mutationFn: (max: number) => updateWorkspace(workspaceId!, { limits: { max_team_members: max } }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workspaces"] });
      toast.success("Limits updated");
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const addMemberMutation = useMutation({
    mutationFn: () => addWorkspaceMember(workspaceId!, memberEmail, memberRole),
    onSuccess: () => {
      setMemberEmail("");
      queryClient.invalidateQueries({ queryKey: ["workspace-members", workspaceId] });
      toast.success("Member added");
    },
    onError: (error) => toast.error(getErrorMessage(error, "Could not add member — they must already have a registered account.")),
  });

  const roleMutation = useMutation({
    mutationFn: ({ memberId, role }: { memberId: string; role: WorkspaceRole }) =>
      updateWorkspaceMemberRole(workspaceId!, memberId, role),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["workspace-members", workspaceId] }),
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const removeMutation = useMutation({
    mutationFn: (memberId: string) => removeWorkspaceMember(workspaceId!, memberId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workspace-members", workspaceId] });
      toast.success("Member removed");
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  if (!activeWorkspace || !workspaceId) {
    return <Skeleton className="h-40 w-full" />;
  }

  return (
    <div className="flex flex-col gap-6">
      <SettingsNav />

      <Card className="flex flex-col gap-4">
        <h2 className="text-base font-semibold text-fg">Plan &amp; limits</h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Field label="Plan">
            <Select
              value={activeWorkspace.plan}
              disabled={!isOwner || planMutation.isPending}
              onValueChange={(v) => planMutation.mutate(v as WorkspacePlan)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {planOptions.map((p) => (
                  <SelectItem key={p} value={p}>
                    {p}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
          <Field label="Max team members" hint="Blank = unlimited">
            <div className="flex gap-2">
              <Input
                type="number"
                min={1}
                disabled={!isOwner}
                placeholder={String(activeWorkspace.limits.max_team_members ?? "unlimited")}
                value={maxTeamMembers}
                onChange={(e) => setMaxTeamMembers(e.target.value)}
                className="flex-1"
              />
              {isOwner && (
                <Button
                  variant="ghost"
                  disabled={!maxTeamMembers}
                  loading={limitsMutation.isPending}
                  onClick={() => limitsMutation.mutate(Number(maxTeamMembers))}
                >
                  Save
                </Button>
              )}
            </div>
          </Field>
        </div>
        {!isOwner && <p className="text-sm text-fgMuted">Only the workspace owner can change plan or limits.</p>}
      </Card>

      <Card className="flex flex-col gap-4">
        <h2 className="text-base font-semibold text-fg">Members</h2>

        {isAdminOrOwner && (
          <form
            className="flex flex-wrap gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (memberEmail.trim()) addMemberMutation.mutate();
            }}
          >
            <Input
              type="email"
              required
              value={memberEmail}
              onChange={(e) => setMemberEmail(e.target.value)}
              placeholder="Existing user's email"
              className="flex-1"
            />
            <Select value={memberRole} onValueChange={(v) => setMemberRole(v as WorkspaceRole)}>
              <SelectTrigger className="w-[140px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {roleOptions
                  .filter((r) => r !== "owner")
                  .map((r) => (
                    <SelectItem key={r} value={r}>
                      {r}
                    </SelectItem>
                  ))}
              </SelectContent>
            </Select>
            <Button type="submit" loading={addMemberMutation.isPending}>
              Add
            </Button>
          </form>
        )}

        <div className="flex flex-col divide-y divide-border">
          {membersQuery.data?.map((member) => {
            const isOnlyOwner =
              member.role === "owner" && membersQuery.data!.filter((m) => m.role === "owner").length === 1;
            return (
              <div key={member.id} className="flex items-center justify-between gap-3 py-3 first:pt-0">
                <span className="text-base text-fg">{member.email ?? member.user_id}</span>
                <div className="flex items-center gap-2">
                  {isOwner ? (
                    <Select
                      value={member.role}
                      disabled={isOnlyOwner || roleMutation.isPending}
                      onValueChange={(v) => roleMutation.mutate({ memberId: member.id, role: v as WorkspaceRole })}
                    >
                      <SelectTrigger className="h-8 w-[110px] text-sm">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {roleOptions.map((r) => (
                          <SelectItem key={r} value={r}>
                            {r}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  ) : (
                    <Pill tone={roleTone[member.role]}>{member.role}</Pill>
                  )}
                  {isAdminOrOwner && !isOnlyOwner && (
                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <Button variant="ghost" size="sm">
                          Remove
                        </Button>
                      </AlertDialogTrigger>
                      <AlertDialogContent>
                        <AlertDialogHeader>
                          <AlertDialogTitle>Remove this member?</AlertDialogTitle>
                          <AlertDialogDescription>
                            {member.email ?? "This member"} will lose access to this workspace immediately.
                          </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel>Keep member</AlertDialogCancel>
                          <AlertDialogAction onClick={() => removeMutation.mutate(member.id)}>Remove</AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
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
    <AppShell title="Settings">
      <WorkspaceSettingsContent />
    </AppShell>
  );
}
