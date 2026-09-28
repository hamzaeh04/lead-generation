"use client";

import { useMutation } from "@tanstack/react-query";
import { Upload } from "lucide-react";
import { useRef, useState } from "react";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import {
  IMPORTABLE_LEAD_FIELDS,
  importLeadsCsv,
  previewLeadsCsv,
  type ImportPreviewResponse,
} from "@/lib/api";
import { getErrorMessage } from "@/lib/errors";

const FIELD_LABELS: Record<(typeof IMPORTABLE_LEAD_FIELDS)[number], string> = {
  company: "Company",
  website: "Website",
  email: "Email",
  first_name: "First name",
  last_name: "Last name",
  job_title: "Job title",
  phone: "Phone",
  city: "City",
  state: "State",
  country: "Country",
  industry: "Industry",
};

const SKIP = "__skip__";

export function ImportLeadsCsvDialog({
  workspaceId,
  batchId,
  onImported,
}: {
  workspaceId: string;
  batchId: string;
  onImported?: () => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportPreviewResponse | null>(null);
  const [mapping, setMapping] = useState<Record<string, string>>({});

  function reset() {
    setFile(null);
    setPreview(null);
    setMapping({});
    if (inputRef.current) inputRef.current.value = "";
  }

  const previewMutation = useMutation({
    mutationFn: (nextFile: File) => previewLeadsCsv(workspaceId, nextFile),
    onSuccess: (data) => {
      setPreview(data);
      setMapping(data.suggested_mapping);
    },
    onError: (error) => toast.error(getErrorMessage(error, "Could not read CSV")),
  });

  const importMutation = useMutation({
    mutationFn: () => {
      if (!file) throw new Error("No file selected");
      const cleaned = Object.fromEntries(
        Object.entries(mapping).filter(([, header]) => header && header !== SKIP)
      );
      return importLeadsCsv(workspaceId, file, cleaned, batchId);
    },
    onSuccess: (result) => {
      toast.success(
        `Imported ${result.contacts_created + result.contacts_matched} lead${
          result.contacts_created + result.contacts_matched === 1 ? "" : "s"
        }` +
          (result.skipped_invalid ? ` · ${result.skipped_invalid} skipped` : "")
      );
      setOpen(false);
      reset();
      onImported?.();
    },
    onError: (error) => toast.error(getErrorMessage(error, "Import failed")),
  });

  return (
    <>
      <Button size="sm" variant="ghost" onClick={() => setOpen(true)}>
        <Upload className="h-3.5 w-3.5" />
        Import CSV
      </Button>
      <Dialog
        open={open}
        onOpenChange={(next) => {
          setOpen(next);
          if (!next) reset();
        }}
      >
        <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Import leads from CSV</DialogTitle>
            <DialogDescription>
              Upload a CSV and map columns. New and existing contacts are added to this batch.
            </DialogDescription>
          </DialogHeader>

          <div className="flex flex-col gap-4">
            <Field label="CSV file">
              <input
                ref={inputRef}
                type="file"
                accept=".csv,text/csv"
                className="block w-full text-sm text-fgMuted file:mr-3 file:rounded-md file:border-0 file:bg-surface2 file:px-3 file:py-1.5 file:text-xs file:font-medium file:text-fg"
                onChange={(e) => {
                  const next = e.target.files?.[0] ?? null;
                  setFile(next);
                  setPreview(null);
                  setMapping({});
                  if (next) previewMutation.mutate(next);
                }}
              />
            </Field>

            {previewMutation.isPending && (
              <p className="text-sm text-fgMuted">Reading CSV…</p>
            )}

            {preview && (
              <>
                <p className="text-sm text-fgMuted">
                  {preview.total_rows} row{preview.total_rows === 1 ? "" : "s"} detected. Map each
                  field to a CSV column:
                </p>
                <div className="grid gap-3">
                  {IMPORTABLE_LEAD_FIELDS.map((field) => (
                    <Field key={field} label={FIELD_LABELS[field]}>
                      <Select
                        value={mapping[field] ?? SKIP}
                        onValueChange={(value) =>
                          setMapping((prev) => {
                            const next = { ...prev };
                            if (value === SKIP) delete next[field];
                            else next[field] = value;
                            return next;
                          })
                        }
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="Skip" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value={SKIP}>Skip</SelectItem>
                          {preview.headers.map((header) => (
                            <SelectItem key={header} value={header}>
                              {header}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </Field>
                  ))}
                </div>
              </>
            )}
          </div>

          <DialogFooter>
            <Button variant="ghost" size="sm" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button
              size="sm"
              loading={importMutation.isPending}
              disabled={!file || !preview || Object.keys(mapping).length === 0}
              onClick={() => importMutation.mutate()}
            >
              Import into batch
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
