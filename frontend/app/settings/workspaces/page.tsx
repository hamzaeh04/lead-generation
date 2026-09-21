"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { AppShell } from "@/components/AppShell";
import { SettingsNav } from "@/components/SettingsNav";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import { Input } from "@/components/ui/Input";
import { Pill } from "@/components/ui/Pill";
import { createWorkspace } from "@/lib/api";
import { getErrorMessage } from "@/lib/errors";
import { useWorkspace } from "@/lib/workspace-context";

function WorkspacesContent() {
  const { workspaces, activeWorkspace, setActiveWorkspaceId } = useWorkspace();
  const queryClient = useQueryClient();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");

  const createMutation = useMutation({
    mutationFn: () => createWorkspace(name),
    onSuccess: async (workspace) => {
      setName("");
      setOpen(false);
      await queryClient.invalidateQueries({ queryKey: ["workspaces"] });
      setActiveWorkspaceId(workspace.id);
      router.push("/dashboard");
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between gap-4">
        <SettingsNav />
        <Dialog open={open} onOpenChange={setOpen}>
          <Button onClick={() => setOpen(true)}>
            <Plus className="h-3.5 w-3.5" />
            New workspace
          </Button>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create a workspace</DialogTitle>
            </DialogHeader>
            <form
              className="flex flex-col gap-4"
              onSubmit={(e) => {
                e.preventDefault();
                if (name.trim()) createMutation.mutate();
              }}
            >
              <Input
                autoFocus
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Client or company name"
              />
              <p className="text-sm text-fgMuted">You become this workspace&apos;s owner.</p>
              <DialogFooter>
                <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
                  Cancel
                </Button>
                <Button type="submit" loading={createMutation.isPending}>
                  Create
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {workspaces.map((ws) => (
          <Card key={ws.id} className="flex flex-col gap-3">
            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="text-md font-medium text-fg">{ws.name}</div>
                <div className="text-sm text-fgMuted">{ws.slug}</div>
              </div>
              {ws.id === activeWorkspace?.id && <Pill tone="accent">active</Pill>}
            </div>
            <div className="flex items-center justify-between">
              <Pill tone="muted">{ws.plan}</Pill>
              {ws.id !== activeWorkspace?.id && (
                <Button variant="ghost" size="sm" onClick={() => setActiveWorkspaceId(ws.id)}>
                  Switch
                </Button>
              )}
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}

export default function WorkspacesPage() {
  return (
    <AppShell title="Workspaces" description="Agency mode — operate several isolated client workspaces from one account.">
      <WorkspacesContent />
    </AppShell>
  );
}
