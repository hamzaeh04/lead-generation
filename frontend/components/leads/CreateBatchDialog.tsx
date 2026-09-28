"use client";

import { useMutation } from "@tanstack/react-query";
import { FolderPlus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import { Field } from "@/components/ui/Label";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import { createSearchBatch } from "@/lib/api";
import { getErrorMessage } from "@/lib/errors";
import { useWorkspace } from "@/lib/workspace-context";

export function CreateBatchDialog({ onCreated }: { onCreated?: (batchId: string) => void }) {
  const { activeWorkspace } = useWorkspace();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  function reset() {
    setName("");
    setDescription("");
  }

  const mutation = useMutation({
    mutationFn: () =>
      createSearchBatch(activeWorkspace!.id, {
        name: name.trim(),
        description: description.trim() || undefined,
      }),
    onSuccess: (batch) => {
      toast.success(`Batch “${batch.name || `Batch ${String(batch.sequence).padStart(2, "0")}`}” created`);
      setOpen(false);
      reset();
      onCreated?.(batch.id);
      router.push(`/leads/batches/${batch.id}`);
    },
    onError: (error) => toast.error(getErrorMessage(error, "Could not create batch")),
  });

  return (
    <>
      <Button size="sm" onClick={() => setOpen(true)}>
        <FolderPlus className="h-3.5 w-3.5" />
        Create batch
      </Button>
      <Dialog
        open={open}
        onOpenChange={(next) => {
          setOpen(next);
          if (!next) reset();
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Create batch</DialogTitle>
            <DialogDescription>
              Name this batch and add optional notes. You can import CSV leads or start a campaign
              from the batch page afterward.
            </DialogDescription>
          </DialogHeader>
          <form
            className="flex flex-col gap-4"
            onSubmit={(e) => {
              e.preventDefault();
              if (!name.trim()) {
                toast.error("Batch name is required");
                return;
              }
              if (!activeWorkspace?.id) {
                toast.error("Select a workspace first");
                return;
              }
              mutation.mutate();
            }}
          >
            <Field label="Batch name" htmlFor="batch_name" hint="Shown in the Leads list and batch header.">
              <Input
                id="batch_name"
                required
                autoFocus
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Q1 dental clinics TX"
                maxLength={255}
              />
            </Field>
            <Field
              label="Description"
              htmlFor="batch_desc"
              hint="Optional — ICP notes, geography, or campaign context."
            >
              <Textarea
                id="batch_desc"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="e.g. Owners and GMs at clinics with 10–50 staff in Texas"
                rows={3}
                maxLength={2000}
              />
            </Field>
            <DialogFooter>
              <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" loading={mutation.isPending} disabled={!name.trim()}>
                Create batch
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
