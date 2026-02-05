import { Outlet } from 'react-router';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { ContextPanel } from './ContextPanel';
import { useSelectionStore } from '@/stores/useSelectionStore';

export function DashboardLayout() {
  const contextPanelOpen = useSelectionStore((s) => s.contextPanelOpen);

  return (
    <div className="flex h-screen bg-surface-base overflow-hidden">
      <Sidebar />
      <div className="flex flex-col flex-1 min-w-0">
        <Header />
        <main className="flex-1 overflow-auto p-4">
          <Outlet />
        </main>
      </div>
      {contextPanelOpen && <ContextPanel />}
    </div>
  );
}
