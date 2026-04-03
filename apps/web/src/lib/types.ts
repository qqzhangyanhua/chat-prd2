export type AuthMode = "login" | "register";

export interface User {
  id: string;
  email: string;
}

export interface AuthResponse {
  user: User;
  access_token: string;
}

export interface SessionResponse {
  id: string;
  user_id: string;
  title: string;
  initial_idea: string;
}

export interface SessionCreateRequest {
  title: string;
  initial_idea: string;
}

export interface SessionListResponse {
  sessions: SessionResponse[];
}

export interface StateSnapshotResponse {
  [key: string]: unknown;
  idea?: string;
  stage_hint?: string;
}

export interface SessionSnapshotResponse {
  session: SessionResponse;
  state: StateSnapshotResponse;
  prd_snapshot: {
    sections: Record<string, Record<string, unknown>>;
  };
}

export interface ExportResponse {
  file_name: string;
  content: string;
}

export interface NextAction {
  action: string;
  reason: string;
  target: string | null;
}

export interface WorkspaceMessage {
  content: string;
  id?: string;
  role: "user" | "assistant";
}

export type PrdSectionStatus = "confirmed" | "inferred" | "missing";

export interface PrdSection {
  content: string;
  status: PrdSectionStatus;
  title: string;
}

export interface PrdState {
  sections: Record<string, PrdSection>;
}

export type WorkspaceEvent =
  | { type: "message.accepted"; data: { message_id: string } }
  | { type: "action.decided"; data: NextAction }
  | { type: "assistant.delta"; data: { delta: string } }
  | { type: "assistant.done"; data: { message_id: string } }
  | { type: "prd.updated"; data: { sections: Record<string, PrdSection> } };
