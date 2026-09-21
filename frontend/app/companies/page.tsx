"use client";

import { useQuery } from "@tanstack/react-query";
import { type ColumnDef } from "@tanstack/react-table";
import { Search } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { Button } from "@/components/ui/Button";
import { DataTable } from "@/components/ui/DataTable";
import { Input } from "@/components/ui/Input";
import { type Company, listCompanies } from "@/lib/api";
import { useWorkspace } from "@/lib/workspace-context";

const PAGE_SIZE = 25;

const columns: ColumnDef<Company, unknown>[] = [
  {
    accessorKey: "name",
    header: "Name",
    cell: ({ row }) => (
      <Link
        href={`/companies/${row.original.id}`}
        className="font-medium text-fg hover:text-accent"
        onClick={(e) => e.stopPropagation()}
      >
        {row.original.name ?? "Unnamed company"}
      </Link>
    ),
  },
  {
    accessorKey: "domain",
    header: "Domain",
    cell: ({ row }) => <span className="text-fgMuted">{row.original.domain ?? "—"}</span>,
  },
  {
    id: "location",
    header: "Location",
    cell: ({ row }) => (
      <span className="text-fgMuted">
        {[row.original.city, row.original.state].filter(Boolean).join(", ") || "—"}
      </span>
    ),
  },
  {
    accessorKey: "industry",
    header: "Industry",
    cell: ({ row }) => <span className="text-fgMuted">{row.original.industry ?? "—"}</span>,
  },
  {
    accessorKey: "employee_count",
    header: "Employees",
    cell: ({ row }) => (
      <span className="font-mono tabular-nums text-fgMuted">{row.original.employee_count ?? "—"}</span>
    ),
  },
  {
    accessorKey: "last_seen",
    header: "Last seen",
    cell: ({ row }) => (
      <span className="text-fgMuted">{new Date(row.original.last_seen).toLocaleDateString()}</span>
    ),
  },
];

function CompaniesContent() {
  const { activeWorkspace } = useWorkspace();
  const router = useRouter();
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [pageIndex, setPageIndex] = useState(0);

  const companiesQuery = useQuery({
    queryKey: ["companies", activeWorkspace?.id, query, pageIndex],
    queryFn: () =>
      listCompanies(activeWorkspace!.id, {
        search: query || undefined,
        limit: PAGE_SIZE,
        offset: pageIndex * PAGE_SIZE,
      }),
    enabled: !!activeWorkspace,
  });

  const companies = useMemo(() => companiesQuery.data ?? [], [companiesQuery.data]);

  return (
    <div className="flex flex-col gap-6">
      <div className="relative max-w-xs">
        <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-fgSubtle" />
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setPageIndex(0);
            setQuery(search);
          }}
        >
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search name or domain…"
            className="pl-8"
          />
        </form>
      </div>

      <DataTable
        columns={columns}
        data={companies}
        getRowId={(row) => row.id}
        isLoading={companiesQuery.isLoading}
        onRowClick={(row) => router.push(`/companies/${row.id}`)}
        emptyTitle={query ? "No companies match that search" : "No companies yet"}
        emptyDescription={
          query
            ? "Try a different name or domain."
            : "Companies are created automatically as you discover leads — run a search to get started."
        }
        emptyAction={
          !query && (
            <Link href="/discover">
              <Button size="sm">Discover leads</Button>
            </Link>
          )
        }
        pagination={{
          pageIndex,
          pageSize: PAGE_SIZE,
          hasNextPage: companies.length === PAGE_SIZE,
          onPageChange: setPageIndex,
        }}
      />
    </div>
  );
}

export default function CompaniesPage() {
  return (
    <AppShell title="Companies" description="Every business discovered or imported into this workspace.">
      <CompaniesContent />
    </AppShell>
  );
}
