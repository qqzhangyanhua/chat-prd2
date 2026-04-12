import { WorkspaceEntry } from "../../components/workspace/workspace-entry";
import { WorkspaceSessionShell } from "../../components/workspace/workspace-session-shell";

interface WorkspacePageProps {
  searchParams: Promise<{ session?: string; initial_idea?: string }>;
}

export default async function WorkspacePage({ searchParams }: WorkspacePageProps) {
  const { session, initial_idea } = await searchParams;

  if (session) {
    return <WorkspaceSessionShell sessionId={session} searchParams={Promise.resolve({ initial_idea })} />;
  }

  return <WorkspaceEntry />;
}
