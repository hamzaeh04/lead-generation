"use client";

import { useQuery } from "@tanstack/react-query";
import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { getCurrentUser, listWorkspaces, type User, type Workspace } from "@/lib/api";

const ACTIVE_WORKSPACE_KEY = "active_workspace_id";

export type AuthStatus = "loading" | "authenticated" | "unauthenticated";

interface WorkspaceContextValue {
  currentUser: User | null;
  workspaces: Workspace[];
  activeWorkspace: Workspace | null;
  setActiveWorkspaceId: (id: string) => void;
  authStatus: AuthStatus;
  refreshAuth: () => void;
}

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

export function WorkspaceProvider({ children }: { children: React.ReactNode }) {
  // Reading localStorage directly during render would differ between the
  // server-rendered HTML (no window) and the client's first paint,
  // producing a hydration mismatch. Instead every render is "unmounted"
  // (server-safe defaults) until this effect runs once on the client,
  // then a normal post-hydration re-render picks up the real values —
  // the same pattern activeId already uses below.
  const [mounted, setMounted] = useState(false);
  const [hasToken, setHasToken] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);

  useEffect(() => {
    setHasToken(!!window.localStorage.getItem("access_token"));
    setActiveId(window.localStorage.getItem(ACTIVE_WORKSPACE_KEY));
    setMounted(true);
  }, []);

  // WorkspaceProvider lives in the root layout and mounts once per page
  // load — a client-side navigation (router.push) never re-runs the
  // effect above, so a token written to localStorage by login/register
  // (or removed by logout) would otherwise go unnoticed until a full page
  // reload. Callers must invoke this right after storeSession()/logout().
  function refreshAuth() {
    setHasToken(!!window.localStorage.getItem("access_token"));
  }

  const userQuery = useQuery({
    queryKey: ["me"],
    queryFn: getCurrentUser,
    retry: false,
    enabled: mounted && hasToken,
  });
  const workspacesQuery = useQuery({
    queryKey: ["workspaces"],
    queryFn: listWorkspaces,
    enabled: userQuery.isSuccess,
  });

  const workspaces = useMemo(() => workspacesQuery.data ?? [], [workspacesQuery.data]);

  const activeWorkspace = useMemo(() => {
    if (workspaces.length === 0) return null;
    return workspaces.find((ws) => ws.id === activeId) ?? workspaces[0];
  }, [workspaces, activeId]);

  function setActiveWorkspaceId(id: string) {
    setActiveId(id);
    window.localStorage.setItem(ACTIVE_WORKSPACE_KEY, id);
  }

  let authStatus: AuthStatus = "loading";
  if (mounted) {
    if (!hasToken) authStatus = "unauthenticated";
    else if (userQuery.isSuccess) authStatus = "authenticated";
    else if (userQuery.isError) authStatus = "unauthenticated";
  }

  // Diagnostic: a token exists but "me" still errored is the one path
  // that bounces a genuinely-logged-in user back to /login (reported:
  // logs in with correct credentials, lands on /dashboard, then gets
  // sent straight back). Every reproduction attempt so far has this call
  // succeed, so the next real occurrence needs to be caught in the
  // wild — this logs exactly what the request/error looked like instead
  // of the app just silently bouncing. Safe to remove once this is
  // root-caused; does nothing when things are working normally.
  useEffect(() => {
    if (mounted && hasToken && userQuery.isError) {
      const err = userQuery.error as { message?: string; response?: { status?: number; data?: unknown } } | undefined;
      // eslint-disable-next-line no-console
      console.error("[auth-debug] /auth/me failed with a token present — bouncing to /login", {
        message: err?.message,
        responseStatus: err?.response?.status,
        responseData: err?.response?.data,
        failureCount: userQuery.failureCount,
        failureReason: userQuery.failureReason,
      });
    }
  }, [mounted, hasToken, userQuery.isError, userQuery.error, userQuery.failureCount, userQuery.failureReason]);

  const value: WorkspaceContextValue = {
    currentUser: userQuery.data ?? null,
    workspaces,
    activeWorkspace,
    setActiveWorkspaceId,
    authStatus,
    refreshAuth,
  };

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

export function useWorkspace() {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) {
    throw new Error("useWorkspace must be used within a WorkspaceProvider");
  }
  return ctx;
}
