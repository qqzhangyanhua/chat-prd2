import { WorkspaceEntry } from "../../components/workspace/workspace-entry";
import { WorkspaceSessionShell } from "../../components/workspace/workspace-session-shell";

interface WorkspacePageProps {
  searchParams: Promise<{ session?: string }>;
}

export default async function WorkspacePage({ searchParams }: WorkspacePageProps) {
  const { session } = await searchParams;

  if (session) {
    return <WorkspaceSessionShell sessionId={session} />;
  }

  return <WorkspaceEntry />;
}
