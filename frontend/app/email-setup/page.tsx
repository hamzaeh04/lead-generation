"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Pill } from "@/components/ui/Pill";
import { Spinner } from "@/components/ui/Spinner";
import { Table, TableBody, TableHead, Td, Th, Tr } from "@/components/ui/Table";
import {
  createEmailSetup,
  deleteEmailSetup,
  getEmailSetupDefaults,
  importEmailSetupsCsv,
  listEmailSetups,
  updateEmailSetup,
  type EmailSetup,
  type EmailSetupCreatePayload,
  type EmailSetupDefaults,
} from "@/lib/api";

const inputClass =
  "rounded-lg border border-border bg-surface px-3 py-2 text-[13px] text-fg placeholder:text-fgMuted focus:border-accent focus:outline-none";

const FALLBACK_DEFAULTS: EmailSetupDefaults = {
  name: "Primary SMTP",
  smtp_host: "smtp.gmail.com",
  smtp_port: 587,
  smtp_email: "you@yourcompany.com",
  smtp_password: "your-smtp-password",
  smtp_use_tls: true,
};

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint: string;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-[13px] font-medium text-fg">{label}</span>
      {children}
      <span className="text-[11.5px] text-fgMuted">{hint}</span>
    </label>
  );
}

type FormState = {
  name: string;
  smtp_host: string;
  smtp_port: number;
  smtp_email: string;
  smtp_password: string;
  smtp_use_tls: boolean;
  is_default: boolean;
};

function emptyForm(defaults: EmailSetupDefaults): FormState {
  return {
    name: "",
    smtp_host: "",
    smtp_port: defaults.smtp_port || 587,
    smtp_email: "",
    smtp_password: "",
    smtp_use_tls: defaults.smtp_use_tls ?? true,
    is_default: false,
  };
}

function formFromSetup(setup: EmailSetup, defaults: EmailSetupDefaults): FormState {
  return {
    name: setup.name,
    smtp_host: setup.smtp_host,
    smtp_port: setup.smtp_port || defaults.smtp_port || 587,
    smtp_email: setup.smtp_email,
    smtp_password: "",
    smtp_use_tls: setup.smtp_use_tls ?? defaults.smtp_use_tls ?? true,
    is_default: setup.is_default,
  };
}

function EmailSetupForm({
  mode,
  defaults,
  initial,
  onCancel,
  onSubmit,
  isPending,
  error,
}: {
  mode: "create" | "edit";
  defaults: EmailSetupDefaults;
  initial: FormState;
  onCancel: () => void;
  onSubmit: (values: FormState) => void;
  isPending: boolean;
  error: boolean;
}) {
  const [form, setForm] = useState<FormState>(initial);

  useEffect(() => {
    setForm(initial);
  }, [initial]);

  function set<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  return (
    <Card className="flex flex-col gap-5">
      <div>
        <h2 className="text-[15px] font-semibold text-fg">
          {mode === "create" ? "Add SMTP account" : "Edit SMTP account"}
        </h2>
        <p className="mt-1 text-[12.5px] text-fgMuted">
          Fields: name, smtp_host, smtp_port, smtp_email, smtp_password, smtp_use_tls.
        </p>
      </div>
      <form
        className="grid grid-cols-1 gap-4 sm:grid-cols-2"
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit(form);
        }}
      >
        <div className="sm:col-span-2">
          <Field label="name" hint="Internal label for this SMTP account.">
            <input
              required
              autoFocus
              value={form.name}
              onChange={(e) => set("name", e.target.value)}
              placeholder={defaults.name}
              className={inputClass}
            />
          </Field>
        </div>
        <Field label="smtp_host" hint="SMTP server hostname.">
          <input
            required
            value={form.smtp_host}
            onChange={(e) => set("smtp_host", e.target.value)}
            placeholder={defaults.smtp_host}
            className={inputClass}
          />
        </Field>
        <Field label="smtp_port" hint="Usually 587 (STARTTLS) or 465 (SSL).">
          <input
            required
            type="number"
            min={1}
            max={65535}
            value={form.smtp_port}
            onChange={(e) => set("smtp_port", Number(e.target.value) || 587)}
            placeholder={String(defaults.smtp_port)}
            className={inputClass}
          />
        </Field>
        <Field label="smtp_email" hint="Login / from email address (must be unique).">
          <input
            required
            type="email"
            value={form.smtp_email}
            onChange={(e) => set("smtp_email", e.target.value)}
            placeholder={defaults.smtp_email}
            className={inputClass}
          />
        </Field>
        <Field
          label="smtp_password"
          hint={
            mode === "edit"
              ? "Leave blank to keep the current password."
              : "SMTP password or app-specific password."
          }
        >
          <input
            required={mode === "create"}
            type="password"
            value={form.smtp_password}
            onChange={(e) => set("smtp_password", e.target.value)}
            placeholder={mode === "edit" ? "••••••••" : defaults.smtp_password}
            className={inputClass}
            autoComplete="new-password"
          />
        </Field>
        <label className="flex items-center gap-2 text-[13px] text-fg sm:col-span-2">
          <input
            type="checkbox"
            checked={form.smtp_use_tls}
            onChange={(e) => set("smtp_use_tls", e.target.checked)}
            className="h-3.5 w-3.5 rounded border-border"
          />
          smtp_use_tls — use STARTTLS (recommended for port 587)
        </label>
        <label className="flex items-center gap-2 text-[13px] text-fg sm:col-span-2">
          <input
            type="checkbox"
            checked={form.is_default}
            onChange={(e) => set("is_default", e.target.checked)}
            className="h-3.5 w-3.5 rounded border-border"
          />
          is_default — set as default SMTP account
        </label>
        <div className="flex items-center gap-2 sm:col-span-2">
          <Button type="submit" disabled={isPending}>
            {isPending ? <Spinner className="h-3.5 w-3.5" /> : mode === "create" ? "Create" : "Save"}
          </Button>
          <Button type="button" variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
          {error && (
            <p className="text-[12.5px] text-danger">
              Could not save — smtp_email may already be in use.
            </p>
          )}
        </div>
      </form>
    </Card>
  );
}

function CsvImportCard({
  onImported,
}: {
  onImported: (result: { created: number; skipped: number }) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [message, setMessage] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (file: File) => importEmailSetupsCsv(file),
    onSuccess: (result) => {
      setMessage(
        `Imported ${result.created} account${result.created === 1 ? "" : "s"}` +
          (result.skipped ? `, skipped ${result.skipped}` : "") +
          "."
      );
      onImported(result);
      if (inputRef.current) inputRef.current.value = "";
    },
    onError: () => {
      setMessage("Import failed — check CSV headers and try again.");
    },
  });

  return (
    <Card className="flex flex-col gap-3">
      <div>
        <h2 className="text-[15px] font-semibold text-fg">Bulk import CSV</h2>
        <p className="mt-1 text-[12.5px] text-fgMuted">
          Columns:{" "}
          <code className="text-fg">
            name, smtp_host, smtp_port, smtp_email, smtp_password, smtp_use_tls
          </code>
          . Port defaults to 587 and TLS to true when omitted.
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <input
          ref={inputRef}
          type="file"
          accept=".csv,text/csv"
          className="text-[12.5px] text-fgMuted file:mr-3 file:rounded-lg file:border file:border-border file:bg-surface file:px-3 file:py-1.5 file:text-[12.5px] file:font-medium file:text-fg hover:file:bg-surface2"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) mutation.mutate(file);
          }}
        />
        {mutation.isPending && <Spinner className="h-3.5 w-3.5" />}
      </div>
      {message && (
        <p className={`text-[12.5px] ${mutation.isError ? "text-danger" : "text-fgMuted"}`}>{message}</p>
      )}
      <a
        href={`data:text/csv;charset=utf-8,${encodeURIComponent(
          "name,smtp_host,smtp_port,smtp_email,smtp_password,smtp_use_tls\nPrimary SMTP,smtp.gmail.com,587,you@yourcompany.com,your-smtp-password,true\n"
        )}`}
        download="email-setup-template.csv"
        className="w-fit text-[12.5px] text-accent hover:underline"
      >
        Download CSV template
      </a>
    </Card>
  );
}

function EmailSetupContent() {
  const queryClient = useQueryClient();
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<EmailSetup | null>(null);

  const defaultsQuery = useQuery({
    queryKey: ["email-setup-defaults"],
    queryFn: () => getEmailSetupDefaults(),
  });

  const listQuery = useQuery({
    queryKey: ["email-setups"],
    queryFn: () => listEmailSetups(),
  });

  const defaults = defaultsQuery.data ?? FALLBACK_DEFAULTS;
  const setups = listQuery.data ?? [];

  const createMutation = useMutation({
    mutationFn: (payload: EmailSetupCreatePayload) => createEmailSetup(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["email-setups"] });
      setFormOpen(false);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Partial<EmailSetupCreatePayload> }) =>
      updateEmailSetup(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["email-setups"] });
      setEditing(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteEmailSetup(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["email-setups"] }),
  });

  function handleCreate(values: FormState) {
    createMutation.mutate({
      name: values.name.trim(),
      smtp_host: values.smtp_host.trim(),
      smtp_port: values.smtp_port,
      smtp_email: values.smtp_email.trim(),
      smtp_password: values.smtp_password,
      smtp_use_tls: values.smtp_use_tls,
      is_default: values.is_default,
    });
  }

  function handleUpdate(values: FormState) {
    if (!editing) return;
    const payload: Partial<EmailSetupCreatePayload> = {
      name: values.name.trim(),
      smtp_host: values.smtp_host.trim(),
      smtp_port: values.smtp_port,
      smtp_email: values.smtp_email.trim(),
      smtp_use_tls: values.smtp_use_tls,
      is_default: values.is_default,
    };
    if (values.smtp_password.trim()) {
      payload.smtp_password = values.smtp_password;
    }
    updateMutation.mutate({ id: editing.id, payload });
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-[22px] font-semibold tracking-tight">Email Setup</h1>
          <p className="mt-1 text-[13px] text-fgMuted">
            Global SMTP accounts — create manually or import a CSV.
          </p>
        </div>
        {!formOpen && !editing && (
          <Button
            onClick={() => {
              setEditing(null);
              setFormOpen(true);
            }}
          >
            Add SMTP
          </Button>
        )}
      </div>

      {!editing && (
        <CsvImportCard onImported={() => queryClient.invalidateQueries({ queryKey: ["email-setups"] })} />
      )}

      {formOpen && (
        <EmailSetupForm
          mode="create"
          defaults={defaults}
          initial={emptyForm(defaults)}
          onCancel={() => setFormOpen(false)}
          onSubmit={handleCreate}
          isPending={createMutation.isPending}
          error={createMutation.isError}
        />
      )}

      {editing && (
        <EmailSetupForm
          mode="edit"
          defaults={defaults}
          initial={formFromSetup(editing, defaults)}
          onCancel={() => setEditing(null)}
          onSubmit={handleUpdate}
          isPending={updateMutation.isPending}
          error={updateMutation.isError}
        />
      )}

      {listQuery.isLoading && (
        <div className="flex items-center gap-2 text-[13px] text-fgMuted">
          <Spinner /> Loading…
        </div>
      )}

      {listQuery.isSuccess && setups.length === 0 && !formOpen && (
        <EmptyState
          title="No SMTP accounts yet"
          description="Add one manually or import a CSV with name, smtp_host, smtp_port, smtp_email, smtp_password, smtp_use_tls."
          action={<Button onClick={() => setFormOpen(true)}>Add your first SMTP account</Button>}
        />
      )}

      {setups.length > 0 && (
        <Table>
          <TableHead>
            <Th>name</Th>
            <Th>smtp_host</Th>
            <Th>smtp_port</Th>
            <Th>smtp_email</Th>
            <Th>smtp_use_tls</Th>
            <Th>is_default</Th>
            <Th />
          </TableHead>
          <TableBody>
            {setups.map((setup) => (
              <Tr key={setup.id}>
                <Td className="font-medium text-fg">{setup.name}</Td>
                <Td className="text-fgMuted">{setup.smtp_host}</Td>
                <Td className="text-fgMuted">{setup.smtp_port}</Td>
                <Td className="text-fgMuted">{setup.smtp_email}</Td>
                <Td>
                  {setup.smtp_use_tls ? (
                    <Pill tone="success">true</Pill>
                  ) : (
                    <Pill tone="muted">false</Pill>
                  )}
                </Td>
                <Td>
                  {setup.is_default ? (
                    <Pill tone="accent">true</Pill>
                  ) : (
                    <span className="text-fgMuted">false</span>
                  )}
                </Td>
                <Td>
                  <div className="flex justify-end gap-2">
                    <Button
                      type="button"
                      variant="ghost"
                      className="px-2.5 py-1.5"
                      onClick={() => {
                        setFormOpen(false);
                        setEditing(setup);
                      }}
                    >
                      Edit
                    </Button>
                    <Button
                      type="button"
                      variant="danger"
                      className="px-2.5 py-1.5"
                      disabled={deleteMutation.isPending}
                      onClick={() => {
                        if (window.confirm(`Delete “${setup.name}”?`)) {
                          deleteMutation.mutate(setup.id);
                        }
                      }}
                    >
                      Delete
                    </Button>
                  </div>
                </Td>
              </Tr>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}

export default function EmailSetupPage() {
  return (
    <AppShell title="Email Setup">
      <EmailSetupContent />
    </AppShell>
  );
}
