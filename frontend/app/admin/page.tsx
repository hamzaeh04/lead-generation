"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ColumnDef } from "@tanstack/react-table";
import Link from "next/link";
import { toast } from "sonner";
import { AppShell } from "@/components/AppShell";
import { Card } from "@/components/ui/Card";
import { Checkbox } from "@/components/ui/Checkbox";
import { DataTable } from "@/components/ui/DataTable";
import { EmptyState } from "@/components/ui/EmptyState";
import { Pill } from "@/components/ui/Pill";
import { TableSkeleton } from "@/components/ui/Skeleton";
import { getAdminProviderPanel, listAllUsers, updateUserSuperuser, type User } from "@/lib/api";
import { getErrorMessage } from "@/lib/errors";
import { useWorkspace } from "@/lib/workspace-context";

function useUserColumns(currentUserId: string | undefined): ColumnDef<User, unknown>[] {
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: ({ user, isSuperuser }: { user: User; isSuperuser: boolean }) =>
      updateUserSuperuser(user.id, isSuperuser),
    onSuccess: (_, { user, isSuperuser }) => {
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      toast.success(`${user.email} is now ${isSuperuser ? "a superuser" : "standard"}`);
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  return [
    {
      accessorKey: "full_name",
      header: "Name",
      cell: ({ row }) => <span className="font-medium text-fg">{row.original.full_name ?? "—"}</span>,
    },
    { accessorKey: "email", header: "Email", cell: ({ row }) => <span className="text-fgMuted">{row.original.email}</span> },
    {
      accessorKey: "is_active",
      header: "Status",
      cell: ({ row }) => (
        <Pill tone={row.original.is_active ? "success" : "muted"}>{row.original.is_active ? "active" : "disabled"}</Pill>
      ),
    },
    {
      accessorKey: "is_superuser",
      header: "Access",
      cell: ({ row }) => {
        const user = row.original;
        const isSelf = user.id === currentUserId;
        return (
          <label className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
            <Checkbox
              checked={user.is_superuser}
              disabled={mutation.isPending || (isSelf && user.is_superuser)}
              onCheckedChange={(checked) => mutation.mutate({ user, isSuperuser: !!checked })}
            />
            <span className="text-sm text-fgMuted">
              {user.is_superuser ? "superuser" : "standard"}
              {isSelf && user.is_superuser && " (you)"}
            </span>
          </label>
        );
      },
    },
  ];
}

function AdminContent() {
  const { currentUser } = useWorkspace();

  const usersQuery = useQuery({ queryKey: ["admin-users"], queryFn: listAllUsers });
  const providersQuery = useQuery({ queryKey: ["admin-providers"], queryFn: getAdminProviderPanel });
  const columns = useUserColumns(currentUser?.id);

  return (
    <div className="flex flex-col gap-8">
      <section className="flex flex-col gap-3">
        <h2 className="text-base font-semibold text-fg">Users</h2>
        {usersQuery.isLoading ? (
          <TableSkeleton cols={4} />
        ) : (
          <DataTable columns={columns} data={usersQuery.data ?? []} getRowId={(u) => u.id} emptyTitle="No users yet" />
        )}
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-base font-semibold text-fg">Provider panel</h2>
        <p className="text-sm text-fgMuted">
          Config and live health merged in one view. Toggle providers from{" "}
          <Link href="/providers" className="text-accent hover:underline">
            Providers
          </Link>
          .
        </p>
        {providersQuery.data && providersQuery.data.length > 0 ? (
          <Card interactive={false} className="flex flex-col divide-y divide-border p-0">
            {providersQuery.data.map((p) => (
              <div key={`${p.provider}:${p.category}`} className="flex items-center justify-between gap-3 px-4 py-3 text-base">
                <span className="font-mono font-medium text-fg">{p.provider}</span>
                <span className="text-fgMuted">{p.category.replace(/_/g, " ")}</span>
                <span className="font-mono tabular-nums text-fgMuted">{Math.round(p.success_rate * 100)}% success</span>
                <span className="font-mono tabular-nums text-fgMuted">
                  {p.quota_remaining !== null ? `${p.quota_remaining} left` : "—"}
                </span>
              </div>
            ))}
          </Card>
        ) : (
          <EmptyState title="No provider activity yet" />
        )}
      </section>
    </div>
  );
}

export default function AdminPage() {
  const { currentUser } = useWorkspace();

  return (
    <AppShell title="Admin" description="Platform-wide — not scoped to a single workspace.">
      {currentUser && !currentUser.is_superuser ? (
        <EmptyState title="Admin access required" description="This area is restricted to platform superusers." />
      ) : (
        <AdminContent />
      )}
    </AppShell>
  );
}
