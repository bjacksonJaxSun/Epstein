import { useAuthStore } from '../stores/useAuthStore';
import type { LoginResponse, RefreshTokenRequest } from '../types/auth';

const BASE_URL = '/api';

// Check if access token is expired or about to expire (within 30 seconds)
function isTokenExpired(): boolean {
  const expiresAt = useAuthStore.getState().accessTokenExpires;
  if (!expiresAt) return true;
  const expiryDate = new Date(expiresAt);
  const now = new Date();
  // Consider expired if less than 30 seconds remaining
  return expiryDate.getTime() - now.getTime() < 30000;
}

// Refresh the access token using the refresh token
let refreshPromise: Promise<boolean> | null = null;

async function refreshAccessToken(): Promise<boolean> {
  // If already refreshing, wait for that to complete
  if (refreshPromise) {
    return refreshPromise;
  }

  const refreshToken = useAuthStore.getState().refreshToken;
  if (!refreshToken) {
    return false;
  }

  refreshPromise = (async () => {
    try {
      const response = await fetch(`${BASE_URL}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refreshToken } as RefreshTokenRequest),
      });

      if (!response.ok) {
        useAuthStore.getState().clearAuth();
        return false;
      }

      const data: LoginResponse = await response.json();
      useAuthStore.getState().updateTokens(
        data.accessToken,
        data.refreshToken,
        data.accessTokenExpires,
        data.refreshTokenExpires
      );
      return true;
    } catch {
      useAuthStore.getState().clearAuth();
      return false;
    } finally {
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

function getAuthHeaders(): HeadersInit {
  const token = useAuthStore.getState().accessToken;
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}

export async function apiGet<T>(
  path: string,
  params?: Record<string, string | number | boolean | undefined>
): Promise<T> {
  // Check if token needs refresh before making request
  if (useAuthStore.getState().accessToken && isTokenExpired()) {
    const refreshed = await refreshAccessToken();
    if (!refreshed) {
      throw new Error('Session expired. Please log in again.');
    }
  }

  const url = new URL(`${BASE_URL}${path}`, window.location.origin);
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) {
        url.searchParams.set(key, String(value));
      }
    });
  }

  const response = await fetch(url.toString(), {
    headers: getAuthHeaders(),
  });

  // Handle 401 by trying to refresh token
  if (response.status === 401) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      // Retry the request with new token
      const retryResponse = await fetch(url.toString(), {
        headers: getAuthHeaders(),
      });
      if (!retryResponse.ok) {
        throw new Error(`API error: ${retryResponse.status} ${retryResponse.statusText}`);
      }
      return retryResponse.json();
    }
    throw new Error('Session expired. Please log in again.');
  }

  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }
  return response.json();
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  // Check if token needs refresh before making request
  if (useAuthStore.getState().accessToken && isTokenExpired()) {
    const refreshed = await refreshAccessToken();
    if (!refreshed) {
      throw new Error('Session expired. Please log in again.');
    }
  }

  const response = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(),
    },
    body: body ? JSON.stringify(body) : undefined,
  });

  // Handle 401 by trying to refresh token
  if (response.status === 401) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      // Retry the request with new token
      const retryResponse = await fetch(`${BASE_URL}${path}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeaders(),
        },
        body: body ? JSON.stringify(body) : undefined,
      });
      if (!retryResponse.ok) {
        throw new Error(`API error: ${retryResponse.status} ${retryResponse.statusText}`);
      }
      return retryResponse.json();
    }
    throw new Error('Session expired. Please log in again.');
  }

  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }
  return response.json();
}

// Public API calls that don't require authentication
export async function apiPostPublic<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.error || `API error: ${response.status} ${response.statusText}`);
  }
  return response.json();
}

export async function apiGetPublic<T>(path: string): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`);
  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }
  return response.json();
}
