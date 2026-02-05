import { useState } from 'react';
import {
  Settings,
  Moon,
  Database,
  Cpu,
  Info,
  Lock,
  ExternalLink,
  ChevronDown,
} from 'lucide-react';
import { cn } from '@/lib/utils';

function SectionHeader({
  icon: Icon,
  title,
}: {
  icon: typeof Settings;
  title: string;
}) {
  return (
    <div className="flex items-center gap-2 border-b border-border-subtle pb-3">
      <Icon className="h-4 w-4 text-text-tertiary" />
      <h3 className="text-sm font-semibold text-text-primary">{title}</h3>
    </div>
  );
}

function SettingRow({
  label,
  description,
  children,
}: {
  label: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-4 py-3">
      <div className="min-w-0">
        <p className="text-sm font-medium text-text-primary">{label}</p>
        {description && (
          <p className="mt-0.5 text-xs text-text-tertiary">{description}</p>
        )}
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  );
}

function SelectDropdown({
  value,
  options,
  onChange,
  disabled,
}: {
  value: string;
  options: { value: string; label: string }[];
  onChange: (value: string) => void;
  disabled?: boolean;
}) {
  return (
    <div className="relative">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className={cn(
          'appearance-none rounded-md border border-border-subtle bg-surface-base py-1.5 pl-3 pr-8 text-sm text-text-primary focus:border-accent-blue focus:outline-none',
          disabled && 'cursor-not-allowed opacity-50'
        )}
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
      <ChevronDown className="pointer-events-none absolute right-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-text-tertiary" />
    </div>
  );
}

function ToggleSwitch({
  checked,
  onChange,
  disabled,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => !disabled && onChange(!checked)}
      disabled={disabled}
      className={cn(
        'relative inline-flex h-6 w-11 shrink-0 rounded-full border-2 border-transparent transition-colors',
        checked ? 'bg-accent-blue' : 'bg-border-default',
        disabled && 'cursor-not-allowed opacity-50'
      )}
    >
      <span
        className={cn(
          'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow-sm transition-transform',
          checked ? 'translate-x-5' : 'translate-x-0'
        )}
      />
    </button>
  );
}

export function SettingsPage() {
  const [darkMode, setDarkMode] = useState(true);
  const [itemsPerPage, setItemsPerPage] = useState('20');
  const [dateFormat, setDateFormat] = useState('mdy');

  return (
    <div className="flex flex-col gap-6">
      {/* Page Header */}
      <div>
        <h2 className="text-xl font-semibold text-text-primary">Settings</h2>
        <p className="mt-1 text-sm text-text-secondary">
          Application preferences, API configuration, and data management.
        </p>
      </div>

      <div className="mx-auto w-full max-w-2xl space-y-6">
        {/* General Settings */}
        <div className="rounded-lg border border-border-subtle bg-surface-raised p-4">
          <SectionHeader icon={Settings} title="General" />

          <SettingRow
            label="Theme"
            description="Application color scheme"
          >
            <div className="flex items-center gap-2">
              <Moon className="h-4 w-4 text-text-tertiary" />
              <ToggleSwitch
                checked={darkMode}
                onChange={setDarkMode}
                disabled
              />
              <span className="text-xs text-text-disabled">Dark only</span>
            </div>
          </SettingRow>

          <div className="border-t border-border-subtle" />

          <SettingRow
            label="Items per page"
            description="Default number of items shown in lists and tables"
          >
            <SelectDropdown
              value={itemsPerPage}
              onChange={setItemsPerPage}
              options={[
                { value: '20', label: '20' },
                { value: '50', label: '50' },
                { value: '100', label: '100' },
              ]}
            />
          </SettingRow>

          <div className="border-t border-border-subtle" />

          <SettingRow
            label="Date format"
            description="How dates are displayed throughout the app"
          >
            <SelectDropdown
              value={dateFormat}
              onChange={setDateFormat}
              options={[
                { value: 'mdy', label: 'MM/DD/YYYY' },
                { value: 'dmy', label: 'DD/MM/YYYY' },
                { value: 'ymd', label: 'YYYY-MM-DD' },
              ]}
            />
          </SettingRow>
        </div>

        {/* Data Settings */}
        <div className="rounded-lg border border-border-subtle bg-surface-raised p-4">
          <SectionHeader icon={Database} title="Data" />

          <SettingRow
            label="Database path"
            description="Location of the SQLite database file"
          >
            <span className="max-w-[200px] truncate rounded-md bg-surface-base px-2.5 py-1 font-mono text-xs text-text-secondary">
              ./data/epstein.db
            </span>
          </SettingRow>

          <div className="border-t border-border-subtle" />

          <SettingRow
            label="Total records"
            description="Number of entities in the database"
          >
            <div className="flex gap-3 text-xs">
              <span className="rounded-md bg-surface-overlay px-2 py-1 text-text-secondary">
                People: --
              </span>
              <span className="rounded-md bg-surface-overlay px-2 py-1 text-text-secondary">
                Docs: --
              </span>
              <span className="rounded-md bg-surface-overlay px-2 py-1 text-text-secondary">
                Events: --
              </span>
            </div>
          </SettingRow>
        </div>

        {/* AI Configuration */}
        <div className="rounded-lg border border-border-subtle bg-surface-raised p-4">
          <div className="flex items-center justify-between border-b border-border-subtle pb-3">
            <div className="flex items-center gap-2">
              <Cpu className="h-4 w-4 text-text-tertiary" />
              <h3 className="text-sm font-semibold text-text-primary">
                AI Configuration
              </h3>
            </div>
            <span className="inline-flex items-center gap-1 rounded-full bg-accent-amber/15 px-2 py-0.5 text-[11px] font-medium text-accent-amber">
              <Lock className="h-3 w-3" />
              Coming Soon
            </span>
          </div>

          <SettingRow
            label="API Provider"
            description="AI model provider for analysis features"
          >
            <SelectDropdown
              value="openai"
              onChange={() => {}}
              disabled
              options={[
                { value: 'openai', label: 'OpenAI' },
                { value: 'claude', label: 'Claude' },
              ]}
            />
          </SettingRow>

          <div className="border-t border-border-subtle" />

          <SettingRow
            label="API Key"
            description="Authentication key for the selected provider"
          >
            <div className="flex flex-col items-end gap-1">
              <input
                type="password"
                disabled
                placeholder="sk-..."
                className="w-40 rounded-md border border-border-subtle bg-surface-base px-2.5 py-1.5 text-sm text-text-disabled placeholder:text-text-disabled"
              />
              <span className="text-[11px] text-text-disabled">
                Configure via environment variables
              </span>
            </div>
          </SettingRow>
        </div>

        {/* About */}
        <div className="rounded-lg border border-border-subtle bg-surface-raised p-4">
          <SectionHeader icon={Info} title="About" />

          <SettingRow label="Version">
            <span className="rounded-md bg-surface-overlay px-2.5 py-1 font-mono text-xs text-text-secondary">
              v0.1.0-alpha
            </span>
          </SettingRow>

          <div className="border-t border-border-subtle" />

          <SettingRow label="Documentation">
            <a
              href="https://github.com"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 text-sm text-accent-blue hover:underline"
            >
              View docs
              <ExternalLink className="h-3.5 w-3.5" />
            </a>
          </SettingRow>

          <div className="border-t border-border-subtle" />

          <SettingRow
            label="Built with"
            description="React, TypeScript, Tailwind CSS, Zustand"
          >
            <span className="text-xs text-text-tertiary">
              .NET 9 + React 19
            </span>
          </SettingRow>
        </div>
      </div>
    </div>
  );
}
