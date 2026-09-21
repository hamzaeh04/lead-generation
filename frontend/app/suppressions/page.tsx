"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ColumnDef } from "@tanstack/react-table";
import { useState } from "react";
import { toast } from "sonner";
import { AppShell } from "@/components/AppShell";
import { Button } from "@/components/ui/Button";
import { DataTable } from "@/components/ui/DataTable";
import { Input } from "@/components/ui/Input";
import { Pill } from "@/components/ui/Pill";
import { createSuppression, listSuppressions, type Suppression, type SuppressionReason } from "@/lib/api";
import { getErrorMessage } from "@/lib/errors";
import { useWorkspace } from "@/lib/workspace-context";

const reasonTone: Record<SuppressionReason, "success" | "warning" | "danger" | "accent" | "muted"> = {
  unsubscribe: "warning",
  bounce: "danger",
  complaint: "danger",
  reply_opt_out: "accent",
  manual: "muted",
};

const columns: ColumnDef<Suppression, unknown>[] = [
  { accessorKey: "email", header: "Email", cell: ({ row }) => <span className="font-medium text-fg">{row.original.email}</span> },
  {
    accessorKey: "reason",
    header: "Reason",
    cell: ({ row }) => <Pill tone={reasonTone[row.original.reason]}>{row.original.reason.replace(/_/g, " ")}</Pill>,
  },
  {
    accessorKey: "created_at",
    header: "Added",
    cell: ({ row }) => <span className="text-fgMuted">{new Date(row.original.created_at).toLocaleDateString()}</span>,
  },
];

function SuppressionsContent() {
  const { activeWorkspace } = useWorkspace();
  const queryClient = useQueryClient();
  const [email, setEmail] = useState("");

  const suppressionsQuery = useQuery({
    queryKey: ["suppressions", activeWorkspace?.id],
    queryFn: () => listSuppressions(activeWorkspace!.id),
    enabled: !!activeWorkspace,
  });

  const mutation = useMutation({
    mutationFn: () => createSuppression(activeWorkspace!.id, email),
    onSuccess: () => {
      setEmail("");
      queryClient.invalidateQueries({ queryKey: ["suppressions", activeWorkspace?.id] });
      toast.success("Added to suppression list");
    },
    onError: (error) => toast.error(getErrorMessage(error, "Could not add suppression.")),
  });

  return (
    <div className="flex flex-col gap-6">
      <form
        className="flex max-w-md gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (email.trim()) mutation.mutate();
        }}
      >
        <Input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="email@example.com"
          className="flex-1"
        />
        <Button type="submit" loading={mutation.isPending}>
          Suppress
        </Button>
      </form>

      <DataTable
        columns={columns}
        data={suppressionsQuery.data ?? []}
        getRowId={(row) => row.id}
        isLoading={suppressionsQuery.isLoading}
        emptyTitle="No suppressions yet"
        emptyDescription="Manually suppressed, unsubscribed, and bounced emails will appear here."
      />
    </div>
  );
}

export default function SuppressionsPage() {
  return (
    <AppShell title="Suppressions" description="The do-not-contact list — checked before every single send, no exceptions.">
      <SuppressionsContent />
    </AppShell>
  );
}
