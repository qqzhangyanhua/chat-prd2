export type AuthMode = "login" | "register";

export interface User {
  id: string;
  email: string;
}

export interface AuthResponse {
  user: User;
  access_token: string;
}
