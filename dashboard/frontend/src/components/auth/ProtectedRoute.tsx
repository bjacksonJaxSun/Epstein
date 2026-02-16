import { Navigate, Outlet } from 'react-router';
import { useAuthStore } from '@/stores/useAuthStore';
import { hasMinimumTier, type RoleTier } from '@/types/auth';

interface ProtectedRouteProps {
  minTier?: RoleTier;
  children?: React.ReactNode;
}

export function ProtectedRoute({ minTier = 'freemium', children }: ProtectedRouteProps) {
  const { accessToken, user } = useAuthStore();

  // Not authenticated - redirect to login
  if (!accessToken) {
    return <Navigate to="/login" replace />;
  }

  // Check tier-based access
  if (user && !hasMinimumTier(user.maxTierLevel, minTier)) {
    return <Navigate to="/unauthorized" replace />;
  }

  // Render children or outlet
  return children ? <>{children}</> : <Outlet />;
}
