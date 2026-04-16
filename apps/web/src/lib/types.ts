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
  completeness?: "complete" | "partial" | "missing";
  entries?: Array<{
    id: string;
    text: string;
    assertion_state: "confirmed" | "inferred" | "to_validate";
    evidence_ref_ids: string[];
  }>;
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
  evidence?: FirstDraftEvidenceItem[] | null;
  critic_result?: CriticResultResponse | null;
  current_model_scene?: RecommendedScene;
  collaboration_mode_label?: string | null;
  response_mode?: GuidanceResponseMode;
  guidance_mode?: GuidanceMode;
  guidance_step?: GuidanceStep;
  focus_dimension?: string | null;
  transition_reason?: string | null;
  option_cards?: DecisionOptionCard[];
  freeform_affordance?: GuidanceFreeformAffordance | null;
  available_mode_switches?: GuidanceModeSwitch[];
  diagnostics?: DecisionDiagnosticItem[];
  diagnostic_summary?: DecisionDiagnosticSummary;
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
export type GuidanceMode = "explore" | "narrow" | "compare" | "confirm";
export type GuidanceStep = "answer" | "choose" | "compare" | "confirm" | "freeform";
export type GuidanceResponseMode = "options_first" | "direct_answer" | "confirm_reply";

export interface SuggestionOption {
  content: string;
  label: string;
  priority: number;
  rationale: string;
  type: string;
}

export interface DecisionOptionCard {
  id: string;
  label: string;
  title: string;
  content: string;
  description: string;
  priority: number;
  type: string;
}

export interface GuidanceFreeformAffordance {
  label: string;
  value: string;
  kind: string;
}

export interface GuidanceModeSwitch {
  mode: string;
  label: string;
}

export type DecisionDiagnosticType = "contradiction" | "gap" | "assumption";
export type DecisionDiagnosticBucket = "unknown" | "risk" | "to_validate";
export type DecisionDiagnosticStatus = "open" | "resolved" | "superseded";

export interface DecisionDiagnosticNextStep {
  action_kind: string;
  label: string;
  prompt: string;
}

export interface DecisionDiagnosticItem {
  id: string;
  type: DecisionDiagnosticType;
  bucket: DecisionDiagnosticBucket;
  status: DecisionDiagnosticStatus;
  title: string;
  detail: string;
  impactScope: string[];
  suggestedNextStep: DecisionDiagnosticNextStep;
  confidence: "high" | "medium" | "low";
}

export interface DecisionDiagnosticSummary {
  openCount: number;
  unknownCount: number;
  riskCount: number;
  toValidateCount: number;
}

export interface DiagnosticLedgerGroup {
  label: string;
  bucket: DecisionDiagnosticBucket;
  items: DecisionDiagnosticItem[];
}

export type AssertionState = "confirmed" | "inferred" | "to_validate";
export type FirstDraftCompleteness = "complete" | "partial" | "missing";

export interface FirstDraftEntry {
  id: string;
  text: string;
  assertionState: AssertionState;
  evidenceRefIds: string[];
}

export interface FirstDraftSection {
  title: string;
  completeness: FirstDraftCompleteness;
  entries: FirstDraftEntry[];
  summary?: string | null;
}

export interface FirstDraftEvidenceItem {
  id: string;
  kind: "user_message" | "assistant_decision" | "system_inference" | "diagnostic";
  excerpt: string;
  sectionKeys: string[];
  messageId?: string | null;
  turnDecisionId?: string | null;
  createdAt?: string | null;
}

export interface FirstDraftUpdateSummary {
  version: number | null;
  sectionKeys: string[];
  entryIds: string[];
  evidenceIds: string[];
}

export interface FirstDraftState {
  version: number | null;
  status: string | null;
  sections: Record<string, FirstDraftSection>;
  evidenceRegistry: Record<string, FirstDraftEvidenceItem>;
  latestUpdates: FirstDraftUpdateSummary;
}

export interface AgentTurnDecisionSectionMeta {
  conversation_strategy?: string;
  strategy_label?: string;
  strategy_reason?: string;
  next_best_questions?: unknown[];
  confirm_quick_replies?: unknown[];
  suggestion_options?: unknown[];
  response_mode?: string;
  guidance_mode?: string;
  guidance_step?: string;
  focus_dimension?: string;
  transition_reason?: string;
  option_cards?: unknown[];
  freeform_affordance?: GuidanceFreeformAffordance | null;
  available_mode_switches?: GuidanceModeSwitch[];
  diagnostics?: unknown[];
  diagnostic_summary?: unknown;
  ledger_summary?: unknown;
  draft_updates?: unknown;
  evidence_ref_ids?: unknown[];
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
  response_mode?: string;
  guidance_mode?: string;
  guidance_step?: string;
  focus_dimension?: string;
  transition_reason?: string;
  option_cards?: unknown[];
  freeform_affordance?: GuidanceFreeformAffordance | null;
  available_mode_switches?: GuidanceModeSwitch[];
  diagnostics?: unknown[];
  diagnostic_summary?: unknown;
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
  guidanceMode: GuidanceMode | null;
  guidanceStep: GuidanceStep | null;
  focusDimension: string | null;
  transitionReason: string | null;
  responseMode: GuidanceResponseMode | null;
  nextBestQuestions: string[];
  confirmQuickReplies?: string[];
  suggestionOptions?: SuggestionOption[];
  optionCards?: DecisionOptionCard[];
  freeformAffordance?: GuidanceFreeformAffordance | null;
  availableModeSwitches?: GuidanceModeSwitch[];
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

export interface DecisionReadyData {
  session_id: string;
  user_message_id: string;
  phase: string;
  conversation_strategy: string;
  next_move: string;
  suggestions: SuggestionOption[];
  recommendation: {
    label: string;
    content: string;
  } | null;
  next_best_questions: string[];
  response_mode?: GuidanceResponseMode;
  guidance_mode?: GuidanceMode;
  guidance_step?: GuidanceStep;
  focus_dimension?: string | null;
  transition_reason?: string | null;
  option_cards?: DecisionOptionCard[];
  freeform_affordance?: GuidanceFreeformAffordance | null;
  available_mode_switches?: GuidanceModeSwitch[];
  diagnostics?: unknown[];
  diagnostic_summary?: unknown;
  ledger_summary?: unknown;
}

export interface DraftUpdatedData {
  sections: Record<string, unknown>;
  evidence_registry?: unknown[];
  draft_summary?: unknown;
  sections_changed?: string[];
  entry_ids?: string[];
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
  | { type: "decision.ready"; data: DecisionReadyData }
  | { type: "draft.updated"; data: DraftUpdatedData }
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
