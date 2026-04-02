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
