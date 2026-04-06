import { WorkspaceEntry } from "../../components/workspace/workspace-entry";
import { WorkspaceSessionShell } from "../../components/workspace/workspace-session-shell";

interface WorkspacePageProps {
  searchParams: Promise<{ session?: string; new?: string }>;
}

export default async function WorkspacePage({ searchParams }: WorkspacePageProps) {
  const { session, new: isNew } = await searchParams;

  if (session) {
    return <WorkspaceSessionShell sessionId={session} />;
  }

  return <WorkspaceEntry autoRedirectToLatest={!isNew} />;
}
