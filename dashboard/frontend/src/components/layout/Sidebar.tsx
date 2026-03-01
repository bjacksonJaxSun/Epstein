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
  Lock,
  Activity,
  Bot,
  Crosshair,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAuthStore } from '@/stores/useAuthStore';
import { hasMinimumTier, type RoleTier } from '@/types/auth';

interface NavItem {
  icon: typeof LayoutDashboard;
  label: string;
  path: string;
  minTier?: RoleTier;
}

const mainNavItems: NavItem[] = [
  { icon: LayoutDashboard, label: 'Overview', path: '/', minTier: 'freemium' },
  { icon: Users, label: 'People', path: '/people', minTier: 'basic' },
  { icon: Building2, label: 'Organizations', path: '/organizations', minTier: 'basic' },
  { icon: GitBranch, label: 'Network', path: '/network', minTier: 'basic' },
  { icon: Calendar, label: 'Timeline', path: '/timeline', minTier: 'basic' },
  { icon: DollarSign, label: 'Financial', path: '/financial', minTier: 'basic' },
  { icon: FileText, label: 'Documents', path: '/documents', minTier: 'basic' },
  { icon: Image, label: 'Media', path: '/media', minTier: 'basic' },
  { icon: MapPin, label: 'Map', path: '/map', minTier: 'basic' },
  { icon: Crosshair, label: 'Investigation', path: '/investigation', minTier: 'basic' },
  { icon: MessageSquare, label: 'Communications', path: '/communications', minTier: 'basic' },
  { icon: Clipboard, label: 'Evidence', path: '/evidence', minTier: 'basic' },
];

const secondaryNavItems: NavItem[] = [
  { icon: Layout, label: 'Boards', path: '/boards', minTier: 'basic' },
  { icon: Bookmark, label: 'Bookmarks', path: '/bookmarks', minTier: 'basic' },
  { icon: Eye, label: 'Vision Analysis', path: '/vision', minTier: 'premium' },
  { icon: Sparkles, label: 'AI Insights', path: '/ai-insights', minTier: 'premium' },
  { icon: Bot, label: 'AI Chat', path: '/ai-chat', minTier: 'premium' },
  { icon: Activity, label: 'Pipeline', path: '/pipeline', minTier: 'admin' },
  { icon: Settings, label: 'Settings', path: '/settings', minTier: 'freemium' },
];

function SidebarLink({
  item,
  expanded,
  hasAccess,
}: {
  item: NavItem;
  expanded: boolean;
  hasAccess: boolean;
}) {
  if (!hasAccess) {
    return (
      <div
        className={cn(
          'group relative flex h-10 items-center gap-3 rounded-md px-3 text-sm font-medium',
          'cursor-not-allowed text-text-disabled opacity-50'
        )}
        title={`Requires ${item.minTier} tier or higher`}
      >
        <item.icon className="h-5 w-5 shrink-0" />
        <span
          className={cn(
            'flex items-center gap-2 whitespace-nowrap transition-all duration-200',
            expanded ? 'opacity-100' : 'w-0 overflow-hidden opacity-0'
          )}
        >
          {item.label}
          <Lock className="h-3 w-3" />
        </span>
      </div>
    );
  }

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
  const user = useAuthStore((state) => state.user);
  const userTier = user?.maxTierLevel ?? 0;

  const canAccess = (minTier: RoleTier = 'freemium') =>
    hasMinimumTier(userTier, minTier);

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
          <SidebarLink
            key={item.path}
            item={item}
            expanded={expanded}
            hasAccess={canAccess(item.minTier)}
          />
        ))}

        {/* Separator */}
        <div className="my-2 border-t border-border-subtle" />

        {secondaryNavItems.map((item) => (
          <SidebarLink
            key={item.path}
            item={item}
            expanded={expanded}
            hasAccess={canAccess(item.minTier)}
          />
        ))}
      </nav>
    </aside>
  );
}
