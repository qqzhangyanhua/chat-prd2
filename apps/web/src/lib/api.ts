import type {
  AdminModelConfigCreateRequest,
  AdminModelConfigItem,
  AdminModelConfigListResponse,
  AdminModelConfigUpdateRequest,
  ApiErrorPayload,
  ApiRecoveryAction,
  AuthResponse,
  EnabledModelConfigListResponse,
  ExportResponse,
  FinalizeSessionRequest,
  HealthStatusResponse,
  SessionCreateRequest,
  SessionListResponse,
  SessionSnapshotResponse,
  SessionUpdateRequest,
} from "./types";
import { useAuthStore } from "../store/auth-store";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
export const SCHEMA_OUTDATED_DETAIL = "数据库结构版本过旧，请先执行 alembic upgrade head";

interface ErrorResponsePayload {
  detail?: string;
  error?: ApiErrorPayload;
}

interface ApiErrorOptions {
  code?: string;
  details?: Record<string, unknown>;
  recoveryAction?: ApiRecoveryAction;
  status: number;
}

export class ApiError extends Error {
  code?: string;
  details?: Record<string, unknown>;
  recoveryAction?: ApiRecoveryAction;
  status: number;

  constructor(message: string, options: ApiErrorOptions) {
    super(message);
    this.name = "ApiError";
    this.code = options.code;
    this.details = options.details;
    this.recoveryAction = options.recoveryAction;
    this.status = options.status;
  }
}

async function getErrorPayload(
  response: Response,
  fallbackMessage: string,
): Promise<{ error?: ApiErrorPayload; message: string }> {
  const errorPayload = (await response.json().catch(() => null)) as
    | ErrorResponsePayload
    | null;
  return {
    error: errorPayload?.error,
    message: errorPayload?.error?.message ?? errorPayload?.detail ?? fallbackMessage,
  };
}

function redirectToLogin(): void {
  useAuthStore.getState().clearAuth();

  if (typeof window !== "undefined") {
    globalThis.location.assign("/login");
  }
}

async function throwApiError(
  response: Response,
  fallbackMessage: string,
  requiresAuth = false,
): Promise<never> {
  const { error, message } = await getErrorPayload(response, fallbackMessage);

  if (requiresAuth && response.status === 401) {
    redirectToLogin();
  }

  throw new ApiError(message, {
    code: error?.code,
    details: error?.details,
    recoveryAction: error?.recovery_action,
    status: response.status,
  });
}

async function requestAuth(
  path: "/api/auth/login" | "/api/auth/register",
  email: string,
  password: string,
): Promise<AuthResponse> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    await throwApiError(response, "认证失败");
  }

  return (await response.json()) as AuthResponse;
}

export function login(email: string, password: string): Promise<AuthResponse> {
  return requestAuth("/api/auth/login", email, password);
}

export function register(email: string, password: string): Promise<AuthResponse> {
  return requestAuth("/api/auth/register", email, password);
}

export async function getHealthStatus(): Promise<HealthStatusResponse> {
  const response = await fetch(`${API_BASE_URL}/api/health`);

  if (response.status === 503) {
    return (await response.json()) as HealthStatusResponse;
  }

  if (!response.ok) {
    await throwApiError(response, "健康检查失败");
  }

  return (await response.json()) as HealthStatusResponse;
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init);

  if (!response.ok) {
    await throwApiError(response, "请求失败", true);
  }

  return (await response.json()) as T;
}

async function requestVoid(path: string, init?: RequestInit): Promise<void> {
  const response = await fetch(`${API_BASE_URL}${path}`, init);

  if (!response.ok) {
    await throwApiError(response, "请求失败", true);
  }
}

export async function sendMessage(
  sessionId: string,
  content: string,
  accessToken?: string | null,
  signal?: AbortSignal,
  modelConfigId?: string,
): Promise<ReadableStream<Uint8Array>> {
  const payload = modelConfigId ? { content, model_config_id: modelConfigId } : { content };
  const response = await fetch(`${API_BASE_URL}/api/sessions/${sessionId}/messages`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    },
    body: JSON.stringify(payload),
    signal,
  });

  if (!response.ok) {
    await throwApiError(response, "消息发送失败", true);
  }

  if (!response.body) {
    throw new Error("消息发送失败");
  }

  return response.body;
}

export async function regenerateMessage(
  sessionId: string,
  userMessageId: string,
  accessToken?: string | null,
  signal?: AbortSignal,
  modelConfigId?: string,
): Promise<ReadableStream<Uint8Array>> {
  if (!modelConfigId) {
    throw new Error("消息重生成失败");
  }

  const response = await fetch(
    `${API_BASE_URL}/api/sessions/${sessionId}/messages/${userMessageId}/regenerate`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      },
      body: JSON.stringify({ model_config_id: modelConfigId }),
      signal,
    },
  );

  if (!response.ok) {
    await throwApiError(response, "消息重生成失败", true);
  }

  if (!response.body) {
    throw new Error("消息重生成失败");
  }

  return response.body;
}

export function exportSession(
  sessionId: string,
  accessToken?: string | null,
): Promise<ExportResponse> {
  return requestJson<ExportResponse>(`/api/sessions/${sessionId}/export`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    },
    body: JSON.stringify({ format: "md" }),
  });
}

export function getSession(
  sessionId: string,
  accessToken?: string | null,
): Promise<SessionSnapshotResponse> {
  return requestJson<SessionSnapshotResponse>(`/api/sessions/${sessionId}`, {
    headers: {
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    },
  });
}

export function listSessions(accessToken?: string | null): Promise<SessionListResponse> {
  return requestJson<SessionListResponse>("/api/sessions", {
    headers: {
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    },
  });
}

export function deleteSession(sessionId: string, accessToken?: string | null): Promise<void> {
  return requestVoid(`/api/sessions/${sessionId}`, {
    method: "DELETE",
    headers: {
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    },
  });
}

export function createSession(
  payload: SessionCreateRequest,
  accessToken?: string | null,
): Promise<SessionSnapshotResponse> {
  return requestJson<SessionSnapshotResponse>("/api/sessions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    },
    body: JSON.stringify(payload),
  });
}

export function updateSession(
  sessionId: string,
  payload: SessionUpdateRequest,
  accessToken?: string | null,
): Promise<SessionSnapshotResponse> {
  return requestJson<SessionSnapshotResponse>(`/api/sessions/${sessionId}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    },
    body: JSON.stringify(payload),
  });
}

export function finalizeSession(
  sessionId: string,
  payload: FinalizeSessionRequest,
  accessToken?: string | null,
): Promise<SessionSnapshotResponse> {
  return requestJson<SessionSnapshotResponse>(`/api/sessions/${sessionId}/finalize`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    },
    body: JSON.stringify(payload),
  });
}

export function listEnabledModelConfigs(
  accessToken?: string | null,
): Promise<EnabledModelConfigListResponse> {
  return requestJson<EnabledModelConfigListResponse>("/api/model-configs/enabled", {
    headers: {
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    },
  });
}

export function listAdminModelConfigs(
  accessToken?: string | null,
): Promise<AdminModelConfigListResponse> {
  return requestJson<AdminModelConfigListResponse>("/api/admin/model-configs", {
    headers: {
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    },
  });
}

export function createAdminModelConfig(
  payload: AdminModelConfigCreateRequest,
  accessToken?: string | null,
): Promise<AdminModelConfigItem> {
  return requestJson<AdminModelConfigItem>("/api/admin/model-configs", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    },
    body: JSON.stringify(payload),
  });
}

export function updateAdminModelConfig(
  configId: string,
  payload: AdminModelConfigUpdateRequest,
  accessToken?: string | null,
): Promise<AdminModelConfigItem> {
  return requestJson<AdminModelConfigItem>(`/api/admin/model-configs/${configId}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    },
    body: JSON.stringify(payload),
  });
}

export function deleteAdminModelConfig(
  configId: string,
  accessToken?: string | null,
): Promise<void> {
  return requestVoid(`/api/admin/model-configs/${configId}`, {
    method: "DELETE",
    headers: {
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    },
  });
}
