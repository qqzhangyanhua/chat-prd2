import { WorkspaceSessionShell } from "../../../components/workspace/workspace-session-shell";


interface WorkspaceSessionPageProps {
  params: Promise<{
    sessionId: string;
  }>;
}


export default async function WorkspaceSessionPage({ params }: WorkspaceSessionPageProps) {
  const { sessionId } = await params;

  return <WorkspaceSessionShell sessionId={sessionId} />;
}
