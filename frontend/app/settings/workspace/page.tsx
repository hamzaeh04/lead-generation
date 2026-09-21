"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
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
import {
  addWorkspaceMember,
  listWorkspaceMembers,
  removeWorkspaceMember,
  updateWorkspace,
  updateWorkspaceMemberRole,
  type WorkspacePlan,
  type WorkspaceRole,
} from "@/lib/api";
import { getErrorMessage } from "@/lib/errors";
import { useWorkspace } from "@/lib/workspace-context";

const roleOptions: WorkspaceRole[] = ["owner", "admin", "member", "viewer"];
const planOptions: WorkspacePlan[] = ["free", "starter", "professional", "agency", "enterprise"];

const roleTone: Record<WorkspaceRole, "success" | "accent" | "muted"> = {
  owner: "success",
  admin: "accent",
  member: "muted",
  viewer: "muted",
};

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
