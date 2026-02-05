import { useQuery } from '@tanstack/react-query';
import { dashboardApi } from '@/api/endpoints/dashboard';

export function useDashboardStats() {
  return useQuery({
    queryKey: ['dashboard', 'stats'],
    queryFn: dashboardApi.getStats,
    staleTime: 60_000,
  });
}
