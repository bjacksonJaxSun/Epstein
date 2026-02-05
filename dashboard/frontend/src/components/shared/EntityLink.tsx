import {
  User,
  Building2,
  MapPin,
  Calendar,
  FileText,
  DollarSign,
} from 'lucide-react';
import { useSelectionStore } from '@/stores/useSelectionStore';
import { cn } from '@/lib/utils';

interface EntityLinkProps {
  id: string | number;
  name: string;
  entityType: string;
  className?: string;
}

const typeConfig: Record<
  string,
  { icon: typeof User; colorClass: string }
> = {
  person: { icon: User, colorClass: 'text-entity-person' },
  organization: { icon: Building2, colorClass: 'text-entity-organization' },
  location: { icon: MapPin, colorClass: 'text-entity-location' },
  event: { icon: Calendar, colorClass: 'text-entity-event' },
  document: { icon: FileText, colorClass: 'text-entity-document' },
  financial: { icon: DollarSign, colorClass: 'text-entity-financial' },
};

export function EntityLink({
  id,
  name,
  entityType,
  className,
}: EntityLinkProps) {
  const selectEntity = useSelectionStore((s) => s.selectEntity);
  const config = typeConfig[entityType] ?? typeConfig.document;
  const Icon = config.icon;

  return (
    <button
      type="button"
      onClick={() => selectEntity(String(id), entityType)}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-sm font-medium transition-colors',
        'hover:bg-surface-overlay focus:outline-none focus:ring-1 focus:ring-accent-blue',
        config.colorClass,
        className
      )}
    >
      <Icon className="h-3.5 w-3.5 shrink-0" />
      <span className="truncate">{name}</span>
    </button>
  );
}
