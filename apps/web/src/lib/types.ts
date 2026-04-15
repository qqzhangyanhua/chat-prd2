export type AuthMode = "login" | "register";

export interface User {
  id: string;
  email: string;
  is_admin: boolean;
}

export interface AuthResponse {
  user: User;
  access_token: string;
}

export interface HealthStatusResponse {
  status: "ok" | "degraded";
  schema: "ready" | "outdated";
  detail?: string;
  missing_tables?: string[];
  error?: ApiErrorPayload;
}

export interface ApiRecoveryAction {
  type: string;
  label: string;
  target: string | null;
}

export interface ApiErrorPayload {
  code: string;
  message: string;
  recovery_action?: ApiRecoveryAction;
  details?: Record<string, unknown>;
}

export interface SessionResponse {
  id: string;
  user_id: string;
  title: string;
  initial_idea: string;
  created_at: string;
  updated_at: string;
}

export interface SessionCreateRequest {
  title: string;
  initial_idea: string;
}

export interface SessionUpdateRequest {
  title: string;
}

export interface SessionListResponse {
  sessions: SessionResponse[];
}

export interface PrdDraftSectionResponse {
  content?: string;
  status?: PrdSectionStatus;
  title?: string;
}

export interface PrdDraftResponse {
  version?: number;
  status?: string;
  sections?: Record<string, PrdDraftSectionResponse>;
}

export interface CriticResultResponse {
  overall_verdict?: string;
  major_gaps?: string[];
  question_queue?: string[];
}

export interface StateSnapshotResponse {
  [key: string]: unknown;
  idea?: string;
  stage_hint?: string;
  workflow_stage?: WorkflowStage;
  finalization_ready?: boolean;
  finalize_confirmation_source?: string | null;
  finalize_preference?: FinalizePreference | null;
  is_completed?: boolean;
  prd_draft?: PrdDraftResponse | null;
  critic_result?: CriticResultResponse | null;
  current_model_scene?: RecommendedScene;
  collaboration_mode_label?: string | null;
}

export interface ConversationMessage {
  id: string;
  session_id: string;
  role: "user" | "assistant";
  content: string;
  message_type: string;
  reply_group_id?: string | null;
  version_no?: number | null;
  is_latest?: boolean | null;
}

export interface AssistantReplyVersion {
  id: string;
  reply_group_id: string;
  session_id: string;
  user_message_id: string;
  version_no: number;
  content: string;
  action_snapshot: Record<string, unknown>;
  model_meta: Record<string, unknown>;
  state_version_id: string | null;
  prd_snapshot_version: number | null;
  created_at: string;
  is_latest?: boolean;
}

export interface AssistantReplyGroup {
  id: string;
  session_id: string;
  user_message_id: string;
  latest_version_id: string | null;
  created_at: string;
  updated_at: string;
  versions: AssistantReplyVersion[];
}

export type DecisionStrategy = "greet" | "clarify" | "choose" | "converge" | "confirm";

export interface SuggestionOption {
  content: string;
  label: string;
  priority: number;
  rationale: string;
  type: string;
}

export interface AgentTurnDecisionSectionMeta {
  conversation_strategy?: string;
  strategy_label?: string;
  strategy_reason?: string;
  next_best_questions?: unknown[];
  confirm_quick_replies?: unknown[];
  suggestion_options?: unknown[];
}

export interface AgentTurnDecisionSection {
  key?: string;
  title?: string;
  content?: string;
  meta?: AgentTurnDecisionSectionMeta;
}

export interface AgentTurnDecisionStatePatch {
  conversation_strategy?: string;
  strategy_label?: string;
  strategy_reason?: string;
  next_best_questions?: unknown[];
  [key: string]: unknown;
}

export interface AgentTurnDecision {
  id: string;
  session_id: string;
  user_message_id?: string | null;
  phase?: string;
  next_move?: string;
  created_at?: string | null;
  decision_sections?: AgentTurnDecisionSection[];
  state_patch_json?: AgentTurnDecisionStatePatch;
}

export interface DecisionGuidance {
  conversationStrategy: DecisionStrategy;
  strategyLabel: string;
  strategyReason: string | null;
  nextBestQuestions: string[];
  confirmQuickReplies?: string[];
  suggestionOptions?: SuggestionOption[];
}

export interface SessionSnapshotResponse {
  session: SessionResponse;
  state: StateSnapshotResponse;
  prd_snapshot: {
    sections: Record<string, Record<string, unknown>>;
  };
  messages: ConversationMessage[];
  assistant_reply_groups?: AssistantReplyGroup[];
  turn_decisions?: AgentTurnDecision[];
}

export interface ExportResponse {
  file_name: string;
  content: string;
}

export interface NextAction {
  action: string;
  reason: string;
  target: string | null;
  observation?: string;
  challenge?: string;
  suggestion?: string;
  question?: string;
}

export interface WorkspaceMessage {
  content: string;
  id?: string;
  isLatest?: boolean | null;
  replyGroupId?: string | null;
  role: "user" | "assistant";
  versionNo?: number | null;
}

export interface EnabledModelConfigItem {
  id: string;
  name: string;
  model: string;
}

export type RecommendedScene = "general" | "reasoning" | "fallback";
export type WorkflowStage = "idea_parser" | "refine_loop" | "finalize" | "completed";
export type FinalizePreference = "balanced" | "business" | "technical";

export interface EnabledModelConfigListResponse {
  items: EnabledModelConfigItem[];
}

export interface AdminModelConfigItem {
  id: string;
  name: string;
  recommended_scene?: RecommendedScene | null;
  recommended_usage?: string | null;
  base_url: string;
  api_key: string;
  model: string;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface AdminModelConfigListResponse {
  items: AdminModelConfigItem[];
}

export interface AdminModelConfigCreateRequest {
  name: string;
  recommended_scene?: RecommendedScene;
  recommended_usage?: string;
  base_url: string;
  api_key: string;
  model: string;
  enabled?: boolean;
}

export interface AdminModelConfigUpdateRequest {
  name?: string;
  recommended_scene?: RecommendedScene;
  recommended_usage?: string;
  base_url?: string;
  api_key?: string;
  model?: string;
  enabled?: boolean;
}

export interface FinalizeSessionRequest {
  confirmation_source: "button" | "message";
  preference?: FinalizePreference;
}

export type PrdSectionStatus = "confirmed" | "inferred" | "missing";

export interface PrdSection {
  content: string;
  status: PrdSectionStatus;
  title: string;
}

export type PrdStageTone = "draft" | "ready" | "final";

export interface PrdMeta {
  stageLabel: string;
  stageTone: PrdStageTone;
  criticSummary: string;
  criticGaps: string[];
  draftVersion: number | null;
  nextQuestion: string | null;
}

export interface PrdState {
  extraSections: Record<string, PrdSection>;
  meta: PrdMeta;
  sections: Record<string, PrdSection>;
}

export type WorkspaceEvent =
  | { type: "message.accepted"; data: { message_id: string; session_id?: string } }
  | {
      type: "reply_group.created";
      data: {
        reply_group_id: string;
        user_message_id: string;
        session_id: string;
        is_regeneration: boolean;
        is_latest: boolean;
      };
    }
  | { type: "action.decided"; data: NextAction }
  | {
      type: "assistant.version.started";
      data: {
        session_id: string;
        user_message_id: string;
        reply_group_id: string;
        assistant_version_id: string;
        version_no: number;
        assistant_message_id: string | null;
        model_config_id: string;
        is_regeneration: boolean;
        is_latest: boolean;
      };
    }
  | {
      type: "assistant.delta";
      data:
        | { delta: string }
        | {
            session_id: string;
            user_message_id: string;
            reply_group_id: string;
            assistant_version_id: string;
            version_no: number;
            assistant_message_id: string | null;
            model_config_id: string;
            delta: string;
            is_regeneration: boolean;
            is_latest: boolean;
          };
    }
  | {
      type: "assistant.done";
      data:
        | { message_id: string }
        | {
            session_id: string;
            user_message_id: string;
            reply_group_id: string;
            assistant_version_id: string;
            version_id: string;
            version_no: number;
            assistant_message_id: string;
            model_config_id: string;
            prd_snapshot_version: number;
            created_at?: string | null;
            is_regeneration: boolean;
            is_latest: boolean;
            message_id?: string;
          };
    }
  | {
      type: "assistant.error";
      data: {
        session_id: string;
        user_message_id: string;
        reply_group_id?: string | null;
        assistant_version_id?: string | null;
        version_no?: number | null;
        model_config_id: string;
        code: string;
        message: string;
        recovery_action: ApiRecoveryAction;
        is_regeneration: boolean;
        is_latest: boolean;
      };
    }
  | {
      type: "prd.updated";
      data: {
        sections: Record<string, PrdSection>;
        meta?: PrdMeta;
      };
    };
