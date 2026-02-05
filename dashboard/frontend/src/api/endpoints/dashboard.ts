import { apiGet } from '../client';
import type { DashboardStats } from '@/types';

export const dashboardApi = {
  getStats: () => apiGet<DashboardStats>('/dashboard/stats'),
};
