import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router';
import { useAuthStore } from '@/stores/useAuthStore';
import { login, logout, getCurrentUser } from '@/api/endpoints/auth';
import type { LoginRequest } from '@/types/auth';

export function useLogin() {
  const navigate = useNavigate();
  const setAuth = useAuthStore((state) => state.setAuth);

  return useMutation({
    mutationFn: (credentials: LoginRequest) => login(credentials),
    onSuccess: (data) => {
      setAuth(
        data.user,
        data.accessToken,
        data.refreshToken,
        data.accessTokenExpires,
        data.refreshTokenExpires
      );
      navigate('/');
    },
  });
}

export function useLogout() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { refreshToken, clearAuth } = useAuthStore();

  return useMutation({
    mutationFn: async () => {
      if (refreshToken) {
        await logout(refreshToken).catch(() => {
          // Ignore errors during logout - we'll clear local state anyway
        });
      }
    },
    onSettled: () => {
      clearAuth();
      queryClient.clear();
      navigate('/login');
    },
  });
}

export function useCurrentUser() {
  const accessToken = useAuthStore((state) => state.accessToken);

  return useQuery({
    queryKey: ['auth', 'me'],
    queryFn: getCurrentUser,
    enabled: !!accessToken,
    staleTime: 5 * 60 * 1000, // 5 minutes
    retry: false,
  });
}

export function useRequireAuth() {
  const navigate = useNavigate();
  const { accessToken, isInitialized, setInitialized } = useAuthStore();

  // Mark as initialized once we've checked
  if (!isInitialized) {
    setInitialized();
  }

  // If no token after initialization, redirect to login
  if (isInitialized && !accessToken) {
    navigate('/login', { replace: true });
    return false;
  }

  return !!accessToken;
}
