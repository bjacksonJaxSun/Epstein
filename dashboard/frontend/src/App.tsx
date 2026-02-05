import { BrowserRouter, Routes, Route } from 'react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'sonner';
import { DashboardLayout } from './components/layout/DashboardLayout';
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
          <Route element={<DashboardLayout />}>
            <Route index element={<DashboardPage />} />
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
            <Route path="ai-insights" element={<AIInsightsPage />} />
            <Route path="settings" element={<SettingsPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
      <Toaster theme="dark" position="bottom-right" />
    </QueryClientProvider>
  );
}
