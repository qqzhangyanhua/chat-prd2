import type {
  AuthResponse,
  ExportResponse,
  SessionCreateRequest,
  SessionListResponse,
  SessionSnapshotResponse,
} from "./types";


const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";


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
    const errorPayload = (await response.json().catch(() => null)) as
      | { detail?: string }
      | null;
    throw new Error(errorPayload?.detail ?? "认证请求失败");
  }

  return (await response.json()) as AuthResponse;
}


export function login(email: string, password: string): Promise<AuthResponse> {
  return requestAuth("/api/auth/login", email, password);
}


export function register(email: string, password: string): Promise<AuthResponse> {
  return requestAuth("/api/auth/register", email, password);
}


async function requestJson<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init);

  if (!response.ok) {
    const errorPayload = (await response.json().catch(() => null)) as
      | { detail?: string }
      | null;
    throw new Error(errorPayload?.detail ?? "请求失败");
  }

  return (await response.json()) as T;
}


export async function sendMessage(
  sessionId: string,
  content: string,
  accessToken?: string | null,
): Promise<ReadableStream<Uint8Array>> {
  const response = await fetch(`${API_BASE_URL}/api/sessions/${sessionId}/messages`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    },
    body: JSON.stringify({ content }),
  });

  if (!response.ok || !response.body) {
    const errorPayload = (await response.json().catch(() => null)) as
      | { detail?: string }
      | null;
    throw new Error(errorPayload?.detail ?? "消息发送失败");
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


export function listSessions(
  accessToken?: string | null,
): Promise<SessionListResponse> {
  return requestJson<SessionListResponse>("/api/sessions", {
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
