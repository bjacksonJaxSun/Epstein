import { BrowserRouter, Routes, Route } from 'react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'sonner';
import { DashboardLayout } from './components/layout/DashboardLayout';
import { ProtectedRoute } from './components/auth/ProtectedRoute';
import {
  DashboardPage,
  PeoplePage,
  PersonDetailPage,
  OrganizationsPage,
  NetworkPage,
  TimelinePage,
  FinancialPage,
  DocumentsPage,
  MediaPage,
  MapPage,
  LocationsPage,
  CommunicationsPage,
  EvidencePage,
  BoardsPage,
  BookmarksPage,
  AIInsightsPage,
  SearchPage,
  SettingsPage,
  VisionAnalysisPage,
  PipelinePage,
  LoginPage,
  UnauthorizedPage,
} from './pages';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          {/* Public routes */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/unauthorized" element={<UnauthorizedPage />} />

          {/* Protected routes - wrapped in ProtectedRoute */}
          <Route element={<ProtectedRoute minTier="freemium" />}>
            <Route element={<DashboardLayout />}>
              {/* Freemium tier - Dashboard overview */}
              <Route index element={<DashboardPage />} />
              <Route path="settings" element={<SettingsPage />} />

              {/* Basic tier - Core content access */}
              <Route element={<ProtectedRoute minTier="basic" />}>
                <Route path="people" element={<PeoplePage />} />
                <Route path="people/:id" element={<PersonDetailPage />} />
                <Route path="organizations" element={<OrganizationsPage />} />
                <Route path="network" element={<NetworkPage />} />
                <Route path="timeline" element={<TimelinePage />} />
                <Route path="financial" element={<FinancialPage />} />
                <Route path="documents" element={<DocumentsPage />} />
                <Route path="media" element={<MediaPage />} />
                <Route path="map" element={<MapPage />} />
                <Route path="locations" element={<LocationsPage />} />
                <Route path="communications" element={<CommunicationsPage />} />
                <Route path="evidence" element={<EvidencePage />} />
                <Route path="boards" element={<BoardsPage />} />
                <Route path="bookmarks" element={<BookmarksPage />} />
                <Route path="search" element={<SearchPage />} />
              </Route>

              {/* Premium tier - AI features */}
              <Route element={<ProtectedRoute minTier="premium" />}>
                <Route path="ai-insights" element={<AIInsightsPage />} />
                <Route path="vision" element={<VisionAnalysisPage />} />
              </Route>

              {/* Admin tier - System monitoring */}
              <Route element={<ProtectedRoute minTier="admin" />}>
                <Route path="pipeline" element={<PipelinePage />} />
              </Route>
            </Route>
          </Route>
        </Routes>
      </BrowserRouter>
      <Toaster theme="dark" position="bottom-right" />
    </QueryClientProvider>
  );
}
