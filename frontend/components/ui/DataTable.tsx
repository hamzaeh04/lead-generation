"use client";

import {
  type ColumnDef,
  type RowSelectionState,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Checkbox } from "@/components/ui/Checkbox";
import { EmptyState } from "@/components/ui/EmptyState";
import { TableSkeleton } from "@/components/ui/Skeleton";
import { Table, TableBody, TableHead, Td, Th, Tr } from "@/components/ui/Table";
import { cn } from "@/lib/cn";

export interface DataTablePagination {
  pageIndex: number;
  pageSize: number;
  hasNextPage: boolean;
  onPageChange: (pageIndex: number) => void;
}

interface DataTableProps<T> {
  columns: ColumnDef<T, unknown>[];
  data: T[];
  getRowId?: (row: T) => string;
  isLoading?: boolean;
  emptyTitle?: string;
  emptyDescription?: string;
  emptyAction?: React.ReactNode;
  onRowClick?: (row: T) => void;
  pagination?: DataTablePagination;
  selectable?: boolean;
  rowSelection?: RowSelectionState;
  onRowSelectionChange?: (selection: RowSelectionState) => void;
  toolbar?: React.ReactNode;
  className?: string;
}

export function DataTable<T>({
  columns,
  data,
  getRowId,
  isLoading,
  emptyTitle = "Nothing here yet",
  emptyDescription,
  emptyAction,
  onRowClick,
  pagination,
  selectable,
  rowSelection,
  onRowSelectionChange,
  toolbar,
  className,
}: DataTableProps<T>) {
  const allColumns: ColumnDef<T, unknown>[] = selectable
    ? [
        {
          id: "__select",
          size: 36,
          header: ({ table }) => (
            <Checkbox
              checked={
                table.getIsAllPageRowsSelected() ||
                (table.getIsSomePageRowsSelected() ? "indeterminate" : false)
              }
              onCheckedChange={(v) => table.toggleAllPageRowsSelected(!!v)}
              onClick={(e) => e.stopPropagation()}
              aria-label="Select all"
            />
          ),
          cell: ({ row }) => (
            <Checkbox
              checked={row.getIsSelected()}
              onCheckedChange={(v) => row.toggleSelected(!!v)}
              onClick={(e) => e.stopPropagation()}
              aria-label="Select row"
            />
          ),
        },
        ...columns,
      ]
    : columns;

  const table = useReactTable({
    data,
    columns: allColumns,
    getCoreRowModel: getCoreRowModel(),
    getRowId,
    state: selectable ? { rowSelection } : undefined,
    onRowSelectionChange: onRowSelectionChange
      ? (updater) =>
          onRowSelectionChange(
            typeof updater === "function" ? updater(rowSelection ?? {}) : updater
          )
      : undefined,
    enableRowSelection: selectable,
  });

  const selectedCount = selectable ? Object.keys(rowSelection ?? {}).length : 0;

  if (isLoading) {
    return <TableSkeleton cols={allColumns.length} />;
  }

  if (data.length === 0) {
    return <EmptyState title={emptyTitle} description={emptyDescription} action={emptyAction} />;
  }

  return (
    <div className={cn("flex flex-col gap-3", className)}>
      {selectedCount > 0 && toolbar && (
        <div className="flex items-center justify-between rounded-lg border border-accentSoft bg-accentSoft px-3.5 py-2 text-sm text-accent">
          <span className="font-medium">{selectedCount} selected</span>
          <div className="flex items-center gap-2">{toolbar}</div>
        </div>
      )}
      <Table>
        <TableHead>
          {table.getHeaderGroups().map((headerGroup) =>
            headerGroup.headers.map((header) => (
              <Th key={header.id} style={{ width: header.getSize() !== 150 ? header.getSize() : undefined }}>
                {header.isPlaceholder
                  ? null
                  : flexRender(header.column.columnDef.header, header.getContext())}
              </Th>
            ))
          )}
        </TableHead>
        <TableBody>
          {table.getRowModel().rows.map((row) => (
            <Tr
              key={row.id}
              onClick={() => onRowClick?.(row.original)}
              className={cn(onRowClick && "cursor-pointer")}
            >
              {row.getVisibleCells().map((cell) => (
                <Td key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</Td>
              ))}
            </Tr>
          ))}
        </TableBody>
      </Table>
      {pagination && (
        <div className="flex items-center justify-between px-1">
          <p className="text-xs text-fgSubtle">
            Showing {data.length === 0 ? 0 : pagination.pageIndex * pagination.pageSize + 1}–
            {pagination.pageIndex * pagination.pageSize + data.length}
          </p>
          <div className="flex items-center gap-1.5">
            <button
              type="button"
              disabled={pagination.pageIndex === 0}
              onClick={() => pagination.onPageChange(pagination.pageIndex - 1)}
              className="flex h-7 w-7 items-center justify-center rounded-md border border-border text-fgMuted hover:bg-surface2 disabled:cursor-not-allowed disabled:opacity-40"
              aria-label="Previous page"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
            </button>
            <span className="min-w-[2ch] text-center text-xs text-fgMuted">{pagination.pageIndex + 1}</span>
            <button
              type="button"
              disabled={!pagination.hasNextPage}
              onClick={() => pagination.onPageChange(pagination.pageIndex + 1)}
              className="flex h-7 w-7 items-center justify-center rounded-md border border-border text-fgMuted hover:bg-surface2 disabled:cursor-not-allowed disabled:opacity-40"
              aria-label="Next page"
            >
              <ChevronRight className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
