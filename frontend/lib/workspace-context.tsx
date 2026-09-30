"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
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
  const queryClient = useQueryClient();
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

  // Auto-logout on session expiry: api.ts's response interceptor clears
  // the stored tokens and fires this event the moment any authenticated
  // request comes back 401 (expired/invalid access token, no working
  // refresh flow to silently extend it). This is the one place that
  // reacts to it — drop the now-dead react-query cache (a stale "me"/
  // workspaces/leads response must never survive into the next login) and
  // tell the user why they landed back on /login, instead of it happening
  // silently.
  useEffect(() => {
    function handleSessionExpired() {
      queryClient.clear();
      setHasToken(false);
      toast.error("Your session has expired. Please log in again.");
    }
    window.addEventListener("auth:session-expired", handleSessionExpired);
    return () => window.removeEventListener("auth:session-expired", handleSessionExpired);
  }, [queryClient]);

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
