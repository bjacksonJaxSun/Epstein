import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Building2,
  Search,
  ChevronLeft,
  ChevronRight,
  AlertCircle,
  X,
  Globe,
  MapPin,
  Users,
  FileText,
  DollarSign,
} from 'lucide-react';
import { organizationsApi } from '@/api/endpoints/organizations';
import type { Organization } from '@/api/endpoints/organizations';
import { apiGet } from '@/api/client';
import { LoadingSpinner } from '@/components/shared';
import { useSelectionStore } from '@/stores/useSelectionStore';
import { cn } from '@/lib/utils';

export function OrganizationsPage() {
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [selectedOrg, setSelectedOrg] = useState<Organization | null>(null);
  const selectEntity = useSelectionStore((s) => s.selectEntity);

  const { data, isLoading, isError } = useQuery({
    queryKey: ['organizations', page, search],
    queryFn: () =>
      organizationsApi.list({
        page,
        pageSize: 20,
        search: search || undefined,
      }),
  });

  const organizations = data?.items ?? [];
  const pagination = data;

  function handleSearch(value: string) {
    setSearch(value);
    setPage(1);
  }

  function handleSelectOrg(org: Organization) {
    setSelectedOrg(org);
    selectEntity(String(org.organizationId), 'organization');
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div>
        <h2 className="text-xl font-semibold text-text-primary">Organizations</h2>
        <p className="mt-1 text-sm text-text-secondary">
          Organizations, companies, and institutions referenced in the documents.
        </p>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-tertiary" />
        <input
          type="text"
          value={search}
          onChange={(e) => handleSearch(e.target.value)}
          placeholder="Search organizations..."
          className="w-full rounded-lg border border-border-subtle bg-surface-raised py-2.5 pl-10 pr-10 text-sm text-text-primary placeholder:text-text-disabled focus:border-accent-blue focus:outline-none focus:ring-1 focus:ring-accent-blue"
        />
        {search && (
          <button
            type="button"
            onClick={() => handleSearch('')}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-text-tertiary hover:text-text-primary"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Content */}
      <div className="flex gap-4">
        {/* Table */}
        <div className={cn('flex-1 rounded-lg border border-border-subtle bg-surface-raised overflow-hidden', selectedOrg && 'w-[65%]')}>
          {isLoading && <LoadingSpinner className="py-24" />}

          {isError && (
            <div className="flex flex-col items-center justify-center gap-3 py-12">
              <AlertCircle className="h-8 w-8 text-accent-red" />
              <p className="text-sm text-accent-red">Failed to load organizations.</p>
            </div>
          )}

          {!isLoading && !isError && organizations.length === 0 && (
            <div className="flex flex-col items-center justify-center gap-3 py-16">
              <Building2 className="h-10 w-10 text-text-disabled" />
              <p className="text-sm text-text-disabled">No organizations found.</p>
            </div>
          )}

          {!isLoading && !isError && organizations.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border-subtle">
                    <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-tertiary">
                      Name
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-tertiary">
                      Type
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-tertiary">
                      Headquarters
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-tertiary">
                      Parent Organization
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-tertiary">
                      Description
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-subtle">
                  {organizations.map((org) => (
                    <tr
                      key={org.organizationId}
                      onClick={() => handleSelectOrg(org)}
                      className={cn(
                        'cursor-pointer transition-colors',
                        selectedOrg?.organizationId === org.organizationId
                          ? 'bg-surface-overlay'
                          : 'hover:bg-surface-overlay'
                      )}
                    >
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <Building2 className="h-4 w-4 text-entity-organization shrink-0" />
                          <span className="text-sm font-medium text-text-primary">
                            {org.organizationName}
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        {org.organizationType ? (
                          <span className="inline-flex items-center rounded-sm border border-border-subtle bg-surface-overlay px-1.5 py-0.5 text-xs text-text-secondary">
                            {org.organizationType}
                          </span>
                        ) : (
                          <span className="text-xs text-text-disabled">--</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-xs text-text-secondary">
                        {org.headquartersLocation ?? '--'}
                      </td>
                      <td className="px-4 py-3 text-xs text-text-secondary">
                        {org.parentOrganization ?? '--'}
                      </td>
                      <td className="px-4 py-3 text-xs text-text-secondary max-w-[200px] truncate">
                        {org.description ?? '--'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Context Panel */}
        {selectedOrg && (
          <OrgDetailPanel
            org={selectedOrg}
            onClose={() => setSelectedOrg(null)}
          />
        )}
      </div>

      {/* Pagination */}
      {pagination && pagination.totalPages > 1 && (
        <div className="flex items-center justify-between rounded-lg border border-border-subtle bg-surface-raised p-3">
          <span className="text-xs text-text-tertiary">
            Page {page} of {pagination.totalPages}
            {' '}({pagination.totalCount.toLocaleString()} total)
          </span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="flex items-center gap-1 rounded-md border border-border-subtle px-2.5 py-1 text-xs text-text-secondary transition-colors hover:bg-surface-overlay disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
              Previous
            </button>
            <button
              type="button"
              onClick={() => setPage((p) => Math.min(pagination.totalPages, p + 1))}
              disabled={page >= pagination.totalPages}
              className="flex items-center gap-1 rounded-md border border-border-subtle px-2.5 py-1 text-xs text-text-secondary transition-colors hover:bg-surface-overlay disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Next
              <ChevronRight className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function OrgDetailPanel({
  org,
  onClose,
}: {
  org: Organization;
  onClose: () => void;
}) {
  // Fetch related data
  const { data: people, isLoading: loadingPeople } = useQuery({
    queryKey: ['organizations', org.organizationId, 'people'],
    queryFn: () => apiGet<Array<{ personId: number; fullName: string; primaryRole?: string }>>(`/organizations/${org.organizationId}/people`),
  });

  const { data: financials, isLoading: loadingFinancials } = useQuery({
    queryKey: ['organizations', org.organizationId, 'financials'],
    queryFn: () => apiGet<Array<{ transactionId: number; amount: number; currency?: string; transactionDate?: string; fromName?: string; toName?: string }>>(`/organizations/${org.organizationId}/financials`),
  });

  const { data: documents, isLoading: loadingDocs } = useQuery({
    queryKey: ['organizations', org.organizationId, 'documents'],
    queryFn: () => apiGet<Array<{ documentId: number; eftaNumber: string; documentType?: string }>>(`/organizations/${org.organizationId}/documents`),
  });

  return (
    <div className="w-[35%] shrink-0 rounded-lg border border-border-subtle bg-surface-raised overflow-y-auto max-h-[calc(100vh-200px)]">
      <div className="flex items-center justify-between border-b border-border-subtle p-4">
        <h3 className="text-sm font-semibold text-text-primary">Organization Details</h3>
        <button
          type="button"
          onClick={onClose}
          className="text-text-tertiary hover:text-text-primary"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="p-4 space-y-4">
        {/* Header */}
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Building2 className="h-5 w-5 text-entity-organization" />
            <h4 className="text-base font-semibold text-text-primary">
              {org.organizationName}
            </h4>
          </div>

          {org.organizationType && (
            <span className="inline-flex items-center rounded-sm border border-entity-organization/30 bg-entity-organization/15 px-1.5 py-0.5 text-xs font-medium text-entity-organization">
              {org.organizationType}
            </span>
          )}
        </div>

        {/* Basic Info */}
        <dl className="flex flex-col gap-2 text-xs">
          {org.headquartersLocation && (
            <div>
              <dt className="flex items-center gap-1 text-text-tertiary mb-0.5">
                <MapPin className="h-3 w-3" /> Headquarters
              </dt>
              <dd className="text-text-secondary">{org.headquartersLocation}</dd>
            </div>
          )}
          {org.parentOrganization && (
            <div>
              <dt className="flex items-center gap-1 text-text-tertiary mb-0.5">
                <Building2 className="h-3 w-3" /> Parent Organization
              </dt>
              <dd className="text-text-secondary">{org.parentOrganization}</dd>
            </div>
          )}
          {org.website && (
            <div>
              <dt className="flex items-center gap-1 text-text-tertiary mb-0.5">
                <Globe className="h-3 w-3" /> Website
              </dt>
              <dd className="text-accent-blue">{org.website}</dd>
            </div>
          )}
          {org.description && (
            <div>
              <dt className="text-text-tertiary mb-0.5">Description</dt>
              <dd className="text-text-secondary leading-relaxed">{org.description}</dd>
            </div>
          )}
        </dl>

        {/* Related People */}
        <div className="border-t border-border-subtle pt-4">
          <h5 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-text-tertiary mb-2">
            <Users className="h-3.5 w-3.5" />
            Related People {people && `(${people.length})`}
          </h5>
          {loadingPeople && <div className="text-xs text-text-disabled">Loading...</div>}
          {!loadingPeople && (!people || people.length === 0) && (
            <div className="text-xs text-text-disabled">No related people found</div>
          )}
          {people && people.length > 0 && (
            <ul className="space-y-1">
              {people.slice(0, 10).map((p) => (
                <li key={p.personId} className="flex items-center gap-2 text-xs">
                  <span className="h-1.5 w-1.5 rounded-full bg-entity-person shrink-0" />
                  <span className="text-text-primary">{p.fullName}</span>
                  {p.primaryRole && <span className="text-text-disabled">({p.primaryRole})</span>}
                </li>
              ))}
              {people.length > 10 && (
                <li className="text-xs text-text-disabled">+{people.length - 10} more</li>
              )}
            </ul>
          )}
        </div>

        {/* Financial Transactions */}
        <div className="border-t border-border-subtle pt-4">
          <h5 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-text-tertiary mb-2">
            <DollarSign className="h-3.5 w-3.5" />
            Financial Transactions {financials && `(${financials.length})`}
          </h5>
          {loadingFinancials && <div className="text-xs text-text-disabled">Loading...</div>}
          {!loadingFinancials && (!financials || financials.length === 0) && (
            <div className="text-xs text-text-disabled">No financial transactions found</div>
          )}
          {financials && financials.length > 0 && (
            <ul className="space-y-1.5">
              {financials.slice(0, 5).map((f) => (
                <li key={f.transactionId} className="text-xs rounded bg-surface-overlay p-2">
                  <div className="flex justify-between items-center">
                    <span className="text-accent-green font-mono">
                      ${f.amount?.toLocaleString() ?? '0'}
                    </span>
                    {f.transactionDate && (
                      <span className="text-text-disabled">{f.transactionDate.split('T')[0]}</span>
                    )}
                  </div>
                  {(f.fromName || f.toName) && (
                    <div className="text-text-tertiary mt-0.5">
                      {f.fromName ?? '?'} → {f.toName ?? '?'}
                    </div>
                  )}
                </li>
              ))}
              {financials.length > 5 && (
                <li className="text-xs text-text-disabled text-center">+{financials.length - 5} more</li>
              )}
            </ul>
          )}
        </div>

        {/* Related Documents */}
        <div className="border-t border-border-subtle pt-4">
          <h5 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-text-tertiary mb-2">
            <FileText className="h-3.5 w-3.5" />
            Documents {documents && `(${documents.length})`}
          </h5>
          {loadingDocs && <div className="text-xs text-text-disabled">Loading...</div>}
          {!loadingDocs && (!documents || documents.length === 0) && (
            <div className="text-xs text-text-disabled">No documents found</div>
          )}
          {documents && documents.length > 0 && (
            <ul className="space-y-1">
              {documents.slice(0, 5).map((d) => (
                <li key={d.documentId}>
                  <a
                    href={`/api/documents/${d.documentId}/file`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 text-xs text-text-secondary hover:text-accent-blue"
                  >
                    <FileText className="h-3 w-3 shrink-0" />
                    <span>{d.eftaNumber}</span>
                    {d.documentType && <span className="text-text-disabled">({d.documentType})</span>}
                  </a>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
