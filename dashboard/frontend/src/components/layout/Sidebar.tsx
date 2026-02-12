import { useState } from 'react';
import { NavLink } from 'react-router';
import {
  LayoutDashboard,
  Users,
  Building2,
  GitBranch,
  Calendar,
  DollarSign,
  FileText,
  Image,
  MapPin,
  MessageSquare,
  Clipboard,
  Layout,
  Bookmark,
  Sparkles,
  Settings,
  Eye,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface NavItem {
  icon: typeof LayoutDashboard;
  label: string;
  path: string;
}

const mainNavItems: NavItem[] = [
  { icon: LayoutDashboard, label: 'Overview', path: '/' },
  { icon: Users, label: 'People', path: '/people' },
  { icon: Building2, label: 'Organizations', path: '/organizations' },
  { icon: GitBranch, label: 'Network', path: '/network' },
  { icon: Calendar, label: 'Timeline', path: '/timeline' },
  { icon: DollarSign, label: 'Financial', path: '/financial' },
  { icon: FileText, label: 'Documents', path: '/documents' },
  { icon: Image, label: 'Media', path: '/media' },
  { icon: MapPin, label: 'Map', path: '/map' },
  { icon: MessageSquare, label: 'Communications', path: '/communications' },
  { icon: Clipboard, label: 'Evidence', path: '/evidence' },
];

const secondaryNavItems: NavItem[] = [
  { icon: Layout, label: 'Boards', path: '/boards' },
  { icon: Bookmark, label: 'Bookmarks', path: '/bookmarks' },
  { icon: Eye, label: 'Vision Analysis', path: '/vision' },
  { icon: Sparkles, label: 'AI Insights', path: '/ai-insights' },
  { icon: Settings, label: 'Settings', path: '/settings' },
];

function SidebarLink({ item, expanded }: { item: NavItem; expanded: boolean }) {
  return (
    <NavLink
      to={item.path}
      end={item.path === '/'}
      className={({ isActive }) =>
        cn(
          'group relative flex h-10 items-center gap-3 rounded-md px-3 text-sm font-medium transition-all',
          'hover:bg-surface-overlay hover:text-text-primary',
          isActive
            ? 'bg-surface-overlay text-accent-blue before:absolute before:left-0 before:top-1 before:h-8 before:w-[3px] before:rounded-r-sm before:bg-accent-blue'
            : 'text-text-secondary'
        )
      }
    >
      <item.icon className="h-5 w-5 shrink-0" />
      <span
        className={cn(
          'whitespace-nowrap transition-all duration-200',
          expanded ? 'opacity-100' : 'w-0 overflow-hidden opacity-0'
        )}
      >
        {item.label}
      </span>
    </NavLink>
  );
}

export function Sidebar() {
  const [expanded, setExpanded] = useState(false);

  return (
    <aside
      onMouseEnter={() => setExpanded(true)}
      onMouseLeave={() => setExpanded(false)}
      className={cn(
        'flex h-full flex-col border-r border-border-subtle bg-surface-raised transition-all duration-200',
        expanded ? 'w-60' : 'w-16'
      )}
    >
      {/* Logo area */}
      <div className="flex h-14 items-center gap-3 border-b border-border-subtle px-4">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-accent-blue/20">
          <GitBranch className="h-4 w-4 text-accent-blue" />
        </div>
        <span
          className={cn(
            'whitespace-nowrap text-sm font-semibold tracking-wide text-text-primary transition-all duration-200',
            expanded ? 'opacity-100' : 'w-0 overflow-hidden opacity-0'
          )}
        >
          INVESTIGATOR
        </span>
      </div>

      {/* Main nav */}
      <nav className="flex flex-1 flex-col gap-1 overflow-y-auto px-2 py-3">
        {mainNavItems.map((item) => (
          <SidebarLink key={item.path} item={item} expanded={expanded} />
        ))}

        {/* Separator */}
        <div className="my-2 border-t border-border-subtle" />

        {secondaryNavItems.map((item) => (
          <SidebarLink key={item.path} item={item} expanded={expanded} />
        ))}
      </nav>
    </aside>
  );
}
