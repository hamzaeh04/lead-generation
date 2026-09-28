"use client";

import { useQueryClient } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { useState } from "react";
import { DiscoverForm } from "@/components/discover/DiscoverForm";
import { Button } from "@/components/ui/Button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import { useWorkspace } from "@/lib/workspace-context";

export function GetLeadsDialog({ onCreated }: { onCreated?: () => void }) {
  const { activeWorkspace } = useWorkspace();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [formKey, setFormKey] = useState(0);

  return (
    <>
      <Button size="sm" variant="ghost" onClick={() => setOpen(true)}>
        <Search className="h-3.5 w-3.5" />
        Get leads
      </Button>
      <Dialog
        open={open}
        onOpenChange={(next) => {
          setOpen(next);
          if (next) setFormKey((k) => k + 1);
        }}
      >
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>Get leads</DialogTitle>
            <DialogDescription>
              Find leads with Apollo or Smartlead — AI prompt or filters, same as Discover. Each
              search creates a new batch.
            </DialogDescription>
          </DialogHeader>
          <DiscoverForm
            key={formKey}
            workspaceId={activeWorkspace?.id}
            showResults
            onBatchCreated={() => {
              queryClient.invalidateQueries({
                queryKey: ["search-batches", activeWorkspace?.id],
              });
              onCreated?.();
            }}
          />
        </DialogContent>
      </Dialog>
    </>
  );
}
