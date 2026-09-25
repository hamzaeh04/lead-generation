"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { LogoMarkIcon } from "@/components/icons";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Label";
import { Input } from "@/components/ui/Input";
import { getErrorMessage } from "@/lib/errors";
import { getCurrentUser, login, storeSession } from "@/lib/api";
import { useWorkspace } from "@/lib/workspace-context";

export default function LoginPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { refreshAuth } = useWorkspace();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const mutation = useMutation({
    mutationFn: login,
    onSuccess: async (data) => {
      storeSession(data);
      // WorkspaceProvider only checks localStorage for a token once, on
      // initial app mount — without this, authStatus would stay
      // "unauthenticated" after a client-side navigation and AppShell
      // would immediately bounce back to /login.
      refreshAuth();
      // Navigating right here used to race WorkspaceProvider's own
      // "me" query — authStatus only becomes "authenticated" after that
      // separate GET /auth/me round trip completes, and depending on a
      // second component's render/effect timing to catch up proved
      // unreliable (intermittently needed 2+ login clicks, or only
      // navigated after a full page reload). Awaiting the same call
      // directly here — into the same react-query cache WorkspaceProvider
      // reads via queryKey ["me"] — makes it deterministic: by the time
      // router.push runs, "me" is already resolved and cached, so
      // WorkspaceProvider reads authStatus "authenticated" on its very
      // first render instead of racing to get there.
      await queryClient.fetchQuery({ queryKey: ["me"], queryFn: getCurrentUser });
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
            <h1 className="text-xl font-semibold tracking-tight text-fg">Welcome back</h1>
            <p className="mt-1 text-sm text-fgMuted">Log in to your workspace to continue.</p>
          </div>
          <form
            className="flex flex-col gap-4"
            onSubmit={(e) => {
              e.preventDefault();
              mutation.mutate({ email, password });
            }}
          >
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
            <Field label="Password" htmlFor="password">
              <Input
                id="password"
                type="password"
                required
                autoComplete="current-password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </Field>
            <Button type="submit" loading={mutation.isPending} className="mt-1 w-full">
              {mutation.isPending ? "Logging in…" : "Log in"}
            </Button>
            {mutation.isError && (
              <p className="text-sm text-danger">{getErrorMessage(mutation.error, "Invalid email or password.")}</p>
            )}
          </form>
        </Card>

        <p className="text-center text-sm text-fgMuted">
          No account?{" "}
          <Link href="/register" className="font-medium text-accent hover:underline">
            Create one
          </Link>
        </p>
      </div>
    </main>
  );
}
