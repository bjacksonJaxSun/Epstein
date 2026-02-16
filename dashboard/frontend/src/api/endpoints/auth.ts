import { apiPost, apiPostPublic, apiGet } from '../client';
import type { LoginRequest, LoginResponse, User } from '../../types/auth';

export async function login(credentials: LoginRequest): Promise<LoginResponse> {
  return apiPostPublic<LoginResponse>('/auth/login', credentials);
}

export async function refreshToken(token: string): Promise<LoginResponse> {
  return apiPostPublic<LoginResponse>('/auth/refresh', { refreshToken: token });
}

export async function logout(refreshToken: string): Promise<void> {
  await apiPost('/auth/logout', { refreshToken });
}

export async function getCurrentUser(): Promise<User> {
  return apiGet<User>('/auth/me');
}
