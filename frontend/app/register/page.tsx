"use client";

import { useMutation } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { LogoMarkIcon } from "@/components/icons";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Label";
import { Input } from "@/components/ui/Input";
import { getErrorMessage } from "@/lib/errors";
import { registerAccount, storeSession } from "@/lib/api";
import { useWorkspace } from "@/lib/workspace-context";

export default function RegisterPage() {
  const router = useRouter();
  const { refreshAuth } = useWorkspace();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [workspaceName, setWorkspaceName] = useState("");

  const mutation = useMutation({
    mutationFn: registerAccount,
    onSuccess: (data) => {
      storeSession(data);
      // See login/page.tsx — WorkspaceProvider's localStorage check only
      // runs once on initial mount, so this must be triggered explicitly.
      refreshAuth();
      router.push("/dashboard");
    },
  });

  return (
    <main className="flex min-h-screen items-center justify-center bg-bg px-6 py-12">
      <div className="flex w-full max-w-[380px] flex-col gap-6">
        <div className="flex items-center justify-center gap-2 text-md font-semibold tracking-tight text-fg">
          <span className="flex h-7 w-7 items-center justify-center rounded-md bg-accent text-white">
            <LogoMarkIcon className="h-3.5 w-3.5" stroke="currentColor" />
          </span>
          Lead Intelligence
        </div>

        <Card className="flex flex-col gap-5 p-7">
          <div>
            <h1 className="text-xl font-semibold tracking-tight text-fg">Create your workspace</h1>
            <p className="mt-1 text-sm text-fgMuted">Start finding and reaching real leads in minutes.</p>
          </div>
          <form
            className="flex flex-col gap-4"
            onSubmit={(e) => {
              e.preventDefault();
              mutation.mutate({
                email,
                password,
                full_name: fullName || undefined,
                workspace_name: workspaceName,
              });
            }}
          >
            <Field label="Workspace name" htmlFor="workspace_name">
              <Input
                id="workspace_name"
                required
                placeholder="Acme Agency"
                value={workspaceName}
                onChange={(e) => setWorkspaceName(e.target.value)}
              />
            </Field>
            <Field label="Full name" htmlFor="full_name" hint="Optional">
              <Input
                id="full_name"
                placeholder="Jordan Alvarez"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
              />
            </Field>
            <Field label="Email" htmlFor="email">
              <Input
                id="email"
                type="email"
                required
                autoComplete="email"
                placeholder="you@company.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </Field>
            <Field label="Password" htmlFor="password" hint="At least 8 characters">
              <Input
                id="password"
                type="password"
                required
                minLength={8}
                autoComplete="new-password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </Field>
            <Button type="submit" loading={mutation.isPending} className="mt-1 w-full">
              {mutation.isPending ? "Creating…" : "Create workspace"}
            </Button>
            {mutation.isError && (
              <p className="text-sm text-danger">
                {getErrorMessage(mutation.error, "Could not create account. Email may already be registered.")}
              </p>
            )}
          </form>
        </Card>

        <p className="text-center text-sm text-fgMuted">
          Already have an account?{" "}
          <Link href="/login" className="font-medium text-accent hover:underline">
            Log in
          </Link>
        </p>
      </div>
    </main>
  );
}
