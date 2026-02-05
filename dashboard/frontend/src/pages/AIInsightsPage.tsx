import {
  Sparkles,
  FileSearch,
  GitBranch,
  TrendingUp,
  ChevronDown,
  Lock,
  User,
  Building2,
  DollarSign,
} from 'lucide-react';
import { cn } from '@/lib/utils';

function ComingSoonBadge() {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-accent-amber/15 px-2 py-0.5 text-[11px] font-medium text-accent-amber">
      <Lock className="h-3 w-3" />
      Coming Soon
    </span>
  );
}

function InsightCard({
  icon: Icon,
  iconColor,
  title,
  description,
  children,
}: {
  icon: typeof Sparkles;
  iconColor: string;
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col rounded-lg border border-border-subtle bg-surface-raised">
      {/* Card header */}
      <div className="border-b border-border-subtle p-4">
        <div className="mb-3 flex items-start justify-between">
          <div
            className={cn(
              'flex h-10 w-10 items-center justify-center rounded-lg',
              iconColor
            )}
          >
            <Icon className="h-5 w-5" />
          </div>
          <ComingSoonBadge />
        </div>
        <h3 className="text-base font-semibold text-text-primary">{title}</h3>
        <p className="mt-1 text-sm text-text-secondary">{description}</p>
      </div>

      {/* Card content */}
      <div className="flex-1 p-4">{children}</div>
    </div>
  );
}

function SampleOutputPreview({
  lines,
}: {
  lines: { label: string; value: string; color?: string }[];
}) {
  return (
    <div className="rounded-md border border-border-subtle bg-surface-base p-3">
      <p className="mb-2 text-[11px] font-medium uppercase tracking-wider text-text-tertiary">
        Sample Output
      </p>
      <div className="flex flex-col gap-1.5">
        {lines.map((line) => (
          <div key={line.label} className="flex items-center justify-between text-xs">
            <span className="text-text-secondary">{line.label}</span>
            <span className={cn('font-medium', line.color ?? 'text-text-primary')}>
              {line.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function AIInsightsPage() {
  return (
    <div className="flex flex-col gap-6">
      {/* Page Header */}
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent-purple/15">
          <Sparkles className="h-5 w-5 text-accent-purple" />
        </div>
        <div>
          <h2 className="text-xl font-semibold text-text-primary">
            AI Insights
          </h2>
          <p className="mt-0.5 text-sm text-text-secondary">
            AI-generated analysis, pattern detection, and anomaly identification.
          </p>
        </div>
      </div>

      {/* Cards Grid */}
      <div className="grid gap-4 lg:grid-cols-3">
        {/* Entity Extraction */}
        <InsightCard
          icon={FileSearch}
          iconColor="bg-accent-blue/15 text-accent-blue"
          title="Entity Extraction"
          description="Extract entities from documents using AI. Automatically identify people, organizations, locations, and dates."
        >
          <div className="flex flex-col gap-3">
            {/* Document selector */}
            <div>
              <label className="mb-1 block text-xs font-medium text-text-tertiary">
                Select Document
              </label>
              <button
                type="button"
                disabled
                className="flex w-full items-center justify-between rounded-md border border-border-subtle bg-surface-base px-3 py-2 text-sm text-text-disabled"
              >
                <span>Choose a document...</span>
                <ChevronDown className="h-4 w-4" />
              </button>
            </div>

            <button
              type="button"
              disabled
              className="flex items-center justify-center gap-2 rounded-md bg-accent-blue/30 px-4 py-2 text-sm font-medium text-accent-blue/50"
            >
              <FileSearch className="h-4 w-4" />
              Analyze Document
            </button>

            <SampleOutputPreview
              lines={[
                { label: 'People detected', value: '12', color: 'text-entity-person' },
                { label: 'Organizations', value: '5', color: 'text-entity-organization' },
                { label: 'Locations', value: '8', color: 'text-entity-location' },
                { label: 'Date references', value: '23', color: 'text-entity-event' },
              ]}
            />
          </div>
        </InsightCard>

        {/* Connection Suggestions */}
        <InsightCard
          icon={GitBranch}
          iconColor="bg-accent-cyan/15 text-accent-cyan"
          title="Connection Suggestions"
          description="Discover hidden connections between people through shared documents, locations, events, and organizations."
        >
          <div className="flex flex-col gap-3">
            {/* Person selector */}
            <div>
              <label className="mb-1 block text-xs font-medium text-text-tertiary">
                Select Person
              </label>
              <button
                type="button"
                disabled
                className="flex w-full items-center justify-between rounded-md border border-border-subtle bg-surface-base px-3 py-2 text-sm text-text-disabled"
              >
                <span>Choose a person...</span>
                <ChevronDown className="h-4 w-4" />
              </button>
            </div>

            <button
              type="button"
              disabled
              className="flex items-center justify-center gap-2 rounded-md bg-accent-cyan/30 px-4 py-2 text-sm font-medium text-accent-cyan/50"
            >
              <GitBranch className="h-4 w-4" />
              Find Connections
            </button>

            <SampleOutputPreview
              lines={[
                { label: 'Direct connections', value: '15', color: 'text-accent-cyan' },
                { label: '2nd degree links', value: '47', color: 'text-accent-blue' },
                { label: 'Shared locations', value: '3', color: 'text-entity-location' },
                { label: 'Confidence', value: 'High', color: 'text-confidence-high' },
              ]}
            />
          </div>
        </InsightCard>

        {/* Pattern Detection */}
        <InsightCard
          icon={TrendingUp}
          iconColor="bg-accent-amber/15 text-accent-amber"
          title="Pattern Detection"
          description="Detect anomalies in financial and behavioral data. Identify unusual transaction patterns and timing correlations."
        >
          <div className="flex flex-col gap-3">
            {/* Analysis type */}
            <div>
              <label className="mb-1 block text-xs font-medium text-text-tertiary">
                Analysis Type
              </label>
              <button
                type="button"
                disabled
                className="flex w-full items-center justify-between rounded-md border border-border-subtle bg-surface-base px-3 py-2 text-sm text-text-disabled"
              >
                <span>Financial patterns</span>
                <ChevronDown className="h-4 w-4" />
              </button>
            </div>

            <button
              type="button"
              disabled
              className="flex items-center justify-center gap-2 rounded-md bg-accent-amber/30 px-4 py-2 text-sm font-medium text-accent-amber/50"
            >
              <TrendingUp className="h-4 w-4" />
              Run Analysis
            </button>

            <SampleOutputPreview
              lines={[
                { label: 'Anomalies detected', value: '7', color: 'text-accent-red' },
                { label: 'Transaction clusters', value: '4', color: 'text-accent-amber' },
                { label: 'Timing correlations', value: '12', color: 'text-accent-blue' },
                { label: 'Risk score', value: '83/100', color: 'text-accent-red' },
              ]}
            />
          </div>
        </InsightCard>
      </div>

      {/* Info footer */}
      <div className="flex items-start gap-3 rounded-lg border border-border-subtle bg-surface-raised p-4">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-accent-purple/15">
          <Sparkles className="h-4 w-4 text-accent-purple" />
        </div>
        <div>
          <p className="text-sm font-medium text-text-primary">
            AI Features Require Configuration
          </p>
          <p className="mt-0.5 text-xs text-text-secondary">
            AI insights require an API key for OpenAI or Claude. Configure your
            provider in{' '}
            <span className="font-medium text-accent-blue">
              Settings &gt; AI Configuration
            </span>{' '}
            to enable these features.
          </p>
          <div className="mt-2 flex gap-4 text-xs text-text-tertiary">
            <span className="flex items-center gap-1">
              <User className="h-3 w-3" /> Entity extraction
            </span>
            <span className="flex items-center gap-1">
              <Building2 className="h-3 w-3" /> Relationship mapping
            </span>
            <span className="flex items-center gap-1">
              <DollarSign className="h-3 w-3" /> Financial analysis
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
