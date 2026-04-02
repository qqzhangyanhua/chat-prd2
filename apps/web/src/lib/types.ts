export type AuthMode = "login" | "register";

export interface User {
  id: string;
  email: string;
}

export interface AuthResponse {
  user: User;
  access_token: string;
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
