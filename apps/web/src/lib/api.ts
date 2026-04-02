import type { AuthResponse } from "./types";


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
