export type RoleTier = 'freemium' | 'basic' | 'premium' | 'admin';

export interface User {
  userId: number;
  username: string;
  email: string;
  roles: string[];
  maxTierLevel: number;
  isActive: boolean;
  lastLoginAt?: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  accessToken: string;
  refreshToken: string;
  accessTokenExpires: string;
  refreshTokenExpires: string;
  user: User;
}

export interface RefreshTokenRequest {
  refreshToken: string;
}

export interface AuthError {
  error: string;
  details?: string;
}

export interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  accessTokenExpires: Date | null;
  refreshTokenExpires: Date | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}

// Tier level mappings
export const TIER_LEVELS: Record<RoleTier, number> = {
  freemium: 0,
  basic: 1,
  premium: 2,
  admin: 3,
};

export const TIER_NAMES: Record<number, RoleTier> = {
  0: 'freemium',
  1: 'basic',
  2: 'premium',
  3: 'admin',
};

export function getTierName(level: number): RoleTier {
  return TIER_NAMES[level] ?? 'freemium';
}

export function hasMinimumTier(userTier: number, requiredTier: RoleTier): boolean {
  return userTier >= TIER_LEVELS[requiredTier];
}
