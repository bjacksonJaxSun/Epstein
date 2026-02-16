import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import type { User } from '../types/auth';

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  accessTokenExpires: string | null;
  refreshTokenExpires: string | null;
  isInitialized: boolean;
}

interface AuthActions {
  setAuth: (
    user: User,
    accessToken: string,
    refreshToken: string,
    accessTokenExpires: string,
    refreshTokenExpires: string
  ) => void;
  updateTokens: (
    accessToken: string,
    refreshToken: string,
    accessTokenExpires: string,
    refreshTokenExpires: string
  ) => void;
  clearAuth: () => void;
  setInitialized: () => void;
}

type AuthStore = AuthState & AuthActions;

const initialState: AuthState = {
  user: null,
  accessToken: null,
  refreshToken: null,
  accessTokenExpires: null,
  refreshTokenExpires: null,
  isInitialized: false,
};

export const useAuthStore = create<AuthStore>()(
  persist(
    (set) => ({
      ...initialState,

      setAuth: (user, accessToken, refreshToken, accessTokenExpires, refreshTokenExpires) =>
        set({
          user,
          accessToken,
          refreshToken,
          accessTokenExpires,
          refreshTokenExpires,
        }),

      updateTokens: (accessToken, refreshToken, accessTokenExpires, refreshTokenExpires) =>
        set({
          accessToken,
          refreshToken,
          accessTokenExpires,
          refreshTokenExpires,
        }),

      clearAuth: () =>
        set({
          user: null,
          accessToken: null,
          refreshToken: null,
          accessTokenExpires: null,
          refreshTokenExpires: null,
        }),

      setInitialized: () => set({ isInitialized: true }),
    }),
    {
      name: 'epstein-auth',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        user: state.user,
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        accessTokenExpires: state.accessTokenExpires,
        refreshTokenExpires: state.refreshTokenExpires,
      }),
    }
  )
);

// Selector hooks for common use cases
export const useUser = () => useAuthStore((state) => state.user);
export const useIsAuthenticated = () => useAuthStore((state) => !!state.accessToken);
export const useUserTier = () => useAuthStore((state) => state.user?.maxTierLevel ?? 0);
