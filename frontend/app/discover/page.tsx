"use client";

import { AppShell } from "@/components/AppShell";
import { DiscoverForm } from "@/components/discover/DiscoverForm";
import { useWorkspace } from "@/lib/workspace-context";

function DiscoverContent() {
  const { activeWorkspace } = useWorkspace();
  return <DiscoverForm workspaceId={activeWorkspace?.id} />;
}

export default function DiscoverPage() {
  return (
    <AppShell
      title="Discover"
      description="Find real leads with Apollo or Smartlead — AI prompt or manual filters."
      fullWidth
    >
      <DiscoverContent />
    </AppShell>
  );
}
