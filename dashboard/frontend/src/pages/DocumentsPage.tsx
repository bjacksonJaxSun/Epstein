import { useState, useCallback, useEffect, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Search,
  FileText,
  ChevronLeft,
  ChevronRight,
  Clock,
  Hash,
  User,
  X,
  AlertCircle,
  Filter,
} from 'lucide-react';
import { format } from 'date-fns';
import { searchApi } from '@/api/endpoints/search';
import { documentsApi } from '@/api/endpoints/documents';
import { LoadingSpinner, ConfidenceBadge, EntityLink } from '@/components/shared';
import { cn } from '@/lib/utils';
import type { Document, SearchResult } from '@/types';

const DOCUMENT_TYPES = [
  'All Types',
  'email',
  'court_filing',
  'financial_record',
  'flight_log',
  'address_book',
  'deposition',
  'police_report',
  'correspondence',
  'legal_document',
  'other',
];

const EXTRACTION_STATUSES = ['All', 'completed', 'partial', 'failed', 'pending'];

function formatFileSize(bytes: number | undefined): string {
  if (!bytes) return '--';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(dateStr: string | undefined): string {
  if (!dateStr) return '--';
  try {
    return format(new Date(dateStr), 'MMM d, yyyy');
  } catch {
    return dateStr;
  }
}

function TypeBadge({ type }: { type: string | undefined }) {
  if (!type) return null;
  const colors: Record<string, string> = {
    email: 'bg-accent-blue/15 text-accent-blue border-accent-blue/30',
    court_filing: 'bg-accent-purple/15 text-accent-purple border-accent-purple/30',
    financial_record: 'bg-entity-financial/15 text-entity-financial border-entity-financial/30',
    flight_log: 'bg-accent-amber/15 text-accent-amber border-accent-amber/30',
    address_book: 'bg-accent-pink/15 text-accent-pink border-accent-pink/30',
    deposition: 'bg-accent-orange/15 text-accent-orange border-accent-orange/30',
    police_report: 'bg-accent-red/15 text-accent-red border-accent-red/30',
  };
  const style = colors[type] ?? 'bg-border-subtle text-text-secondary border-border-default';

  return (
    <span
      className={cn(
        'inline-flex items-center rounded-sm border px-1.5 py-0.5 text-xs font-medium',
        style
      )}
    >
      {type.replace(/_/g, ' ')}
    </span>
  );
}

export function DocumentsPage() {
  const [searchInput, setSearchInput] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [page, setPage] = useState(1);
  const [docType, setDocType] = useState('All Types');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [extractionStatus, setExtractionStatus] = useState('All');
  const [selectedDocId, setSelectedDocId] = useState<number | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const searchStartRef = useRef<number>(0);
  const [searchTime, setSearchTime] = useState<number | null>(null);

  const handleSearchInput = useCallback((value: string) => {
    setSearchInput(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      searchStartRef.current = Date.now();
      setSearchQuery(value);
      setPage(1);
    }, 300);
  }, []);

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  const isSearchMode = searchQuery.trim().length > 0;

  const searchResults = useQuery({
    queryKey: ['document-search', searchQuery, page],
    queryFn: async () => {
      const result = await searchApi.fullText({
        query: searchQuery,
        page,
        pageSize: 20,
      });
      if (searchStartRef.current > 0) {
        setSearchTime(Date.now() - searchStartRef.current);
        searchStartRef.current = 0;
      }
      return result;
    },
    enabled: isSearchMode,
  });

  const browseResults = useQuery({
    queryKey: ['documents-browse', page, docType, dateFrom, dateTo, extractionStatus],
    queryFn: () =>
      documentsApi.list({
        page,
        pageSize: 20,
        documentType: docType !== 'All Types' ? docType : undefined,
        search: undefined,
      }),
    enabled: !isSearchMode,
  });

  const selectedDocument = useQuery({
    queryKey: ['document-detail', selectedDocId],
    queryFn: () => documentsApi.getById(selectedDocId!),
    enabled: selectedDocId !== null,
  });

  const activeData = isSearchMode ? searchResults : browseResults;
  const items = activeData.data?.items ?? [];
  const pagination = activeData.data;

  function handleSelectDocument(docId: number) {
    setSelectedDocId(docId);
  }

  function renderSearchResultCard(result: SearchResult) {
    const isSelected = selectedDocId === result.documentId;
    return (
      <button
        key={result.documentId}
        type="button"
        onClick={() => handleSelectDocument(result.documentId)}
        className={cn(
          'w-full rounded-lg border-l-2 p-4 text-left transition-colors',
          isSelected
            ? 'border-accent-blue bg-surface-overlay'
            : 'border-transparent bg-surface-raised hover:border-accent-blue hover:bg-surface-overlay'
        )}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono text-text-tertiary">
                {result.eftaNumber}
              </span>
              <TypeBadge type={result.documentType} />
            </div>
            <h4 className="mt-1 text-sm font-medium text-text-primary truncate">
              {result.title ?? 'Untitled Document'}
            </h4>
            {result.documentDate && (
              <span className="mt-0.5 text-xs text-text-tertiary">
                {formatDate(result.documentDate)}
              </span>
            )}
            {result.snippet && (
              <p
                className="mt-2 text-xs text-text-secondary line-clamp-3"
                dangerouslySetInnerHTML={{
                  __html: result.snippet.replace(
                    /<mark>/g,
                    '<mark class="bg-accent-amber/30 text-accent-amber rounded-sm px-0.5">'
                  ),
                }}
              />
            )}
          </div>
          <div className="flex flex-col items-end gap-1 shrink-0">
            <span className="text-xs text-text-tertiary">
              {(result.relevanceScore * 100).toFixed(0)}%
            </span>
          </div>
        </div>
      </button>
    );
  }

  function renderDocumentCard(doc: Document) {
    const isSelected = selectedDocId === doc.documentId;
    return (
      <button
        key={doc.documentId}
        type="button"
        onClick={() => handleSelectDocument(doc.documentId)}
        className={cn(
          'w-full rounded-lg border-l-2 p-4 text-left transition-colors',
          isSelected
            ? 'border-accent-blue bg-surface-overlay'
            : 'border-transparent bg-surface-raised hover:border-accent-blue hover:bg-surface-overlay'
        )}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono text-text-tertiary">
                {doc.eftaNumber}
              </span>
              <TypeBadge type={doc.documentType} />
              {doc.isRedacted && (
                <span className="inline-flex items-center rounded-sm border border-accent-red/30 bg-accent-red/15 px-1.5 py-0.5 text-xs font-medium text-accent-red">
                  REDACTED
                </span>
              )}
            </div>
            <h4 className="mt-1 text-sm font-medium text-text-primary truncate">
              {doc.documentTitle ?? 'Untitled Document'}
            </h4>
            <div className="mt-1 flex items-center gap-3 text-xs text-text-tertiary">
              {doc.documentDate && <span>{formatDate(doc.documentDate)}</span>}
              {doc.pageCount && <span>{doc.pageCount} pages</span>}
              {doc.fileSizeBytes && <span>{formatFileSize(doc.fileSizeBytes)}</span>}
            </div>
          </div>
          {doc.extractionConfidence !== undefined && (
            <ConfidenceBadge
              level={
                doc.extractionConfidence >= 0.8
                  ? 'high'
                  : doc.extractionConfidence >= 0.5
                    ? 'medium'
                    : 'low'
              }
            />
          )}
        </div>
      </button>
    );
  }

  return (
    <div className="flex flex-col gap-4 h-full">
      {/* Header */}
      <div>
        <h2 className="text-xl font-semibold text-text-primary">Documents</h2>
        <p className="mt-1 text-sm text-text-secondary">
          Full-text search and browse all extracted documents with metadata.
        </p>
      </div>

      {/* Search Bar */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-tertiary" />
        <input
          type="text"
          value={searchInput}
          onChange={(e) => handleSearchInput(e.target.value)}
          placeholder="Search documents by content, title, EFTA number..."
          className="w-full rounded-lg border border-border-subtle bg-surface-raised py-2.5 pl-10 pr-10 text-sm text-text-primary placeholder:text-text-disabled focus:border-accent-blue focus:outline-none focus:ring-1 focus:ring-accent-blue"
        />
        {searchInput && (
          <button
            type="button"
            onClick={() => {
              setSearchInput('');
              setSearchQuery('');
              setSearchTime(null);
              setPage(1);
            }}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-text-tertiary hover:text-text-primary"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Search stats */}
      {isSearchMode && searchResults.data && (
        <div className="flex items-center gap-2 text-xs text-text-tertiary">
          <Clock className="h-3 w-3" />
          <span>
            {pagination?.totalCount.toLocaleString() ?? 0} results
            {searchTime !== null && ` in ${(searchTime / 1000).toFixed(2)}s`}
          </span>
        </div>
      )}

      {/* Filter Row */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-1.5 text-xs text-text-tertiary">
          <Filter className="h-3.5 w-3.5" />
          <span>Filters:</span>
        </div>
        <select
          value={docType}
          onChange={(e) => { setDocType(e.target.value); setPage(1); }}
          className="rounded-md border border-border-subtle bg-surface-raised px-2.5 py-1.5 text-xs text-text-primary focus:border-accent-blue focus:outline-none"
        >
          {DOCUMENT_TYPES.map((t) => (
            <option key={t} value={t}>{t === 'All Types' ? t : t.replace(/_/g, ' ')}</option>
          ))}
        </select>
        <div className="flex items-center gap-1.5">
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => { setDateFrom(e.target.value); setPage(1); }}
            className="rounded-md border border-border-subtle bg-surface-raised px-2 py-1.5 text-xs text-text-primary focus:border-accent-blue focus:outline-none [color-scheme:dark]"
            placeholder="From"
          />
          <span className="text-xs text-text-tertiary">to</span>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => { setDateTo(e.target.value); setPage(1); }}
            className="rounded-md border border-border-subtle bg-surface-raised px-2 py-1.5 text-xs text-text-primary focus:border-accent-blue focus:outline-none [color-scheme:dark]"
            placeholder="To"
          />
        </div>
        <select
          value={extractionStatus}
          onChange={(e) => { setExtractionStatus(e.target.value); setPage(1); }}
          className="rounded-md border border-border-subtle bg-surface-raised px-2.5 py-1.5 text-xs text-text-primary focus:border-accent-blue focus:outline-none"
        >
          {EXTRACTION_STATUSES.map((s) => (
            <option key={s} value={s}>{s === 'All' ? 'All Statuses' : s}</option>
          ))}
        </select>
      </div>

      {/* Split Panel: Results + Viewer */}
      <div className="flex flex-1 gap-4 min-h-0" style={{ height: 'calc(100vh - 320px)' }}>
        {/* Left Panel - Results List */}
        <div className="flex w-[60%] flex-col gap-2 overflow-y-auto pr-1">
          {activeData.isLoading && (
            <LoadingSpinner className="py-24" />
          )}

          {activeData.isError && (
            <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-accent-red/30 bg-accent-red/5 py-12">
              <AlertCircle className="h-8 w-8 text-accent-red" />
              <p className="text-sm text-accent-red">Failed to load documents. Please try again.</p>
            </div>
          )}

          {activeData.isSuccess && items.length === 0 && (
            <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-border-subtle bg-surface-raised py-16">
              <FileText className="h-10 w-10 text-text-disabled" />
              <p className="text-sm text-text-disabled">
                {isSearchMode ? 'No documents match your search.' : 'No documents found.'}
              </p>
            </div>
          )}

          {activeData.isSuccess && items.length > 0 && (
            <>
              <div className="flex flex-col gap-2">
                {isSearchMode
                  ? (items as SearchResult[]).map(renderSearchResultCard)
                  : (items as Document[]).map(renderDocumentCard)}
              </div>

              {/* Pagination */}
              {pagination && pagination.totalPages > 1 && (
                <div className="flex items-center justify-between rounded-lg border border-border-subtle bg-surface-raised p-3 mt-2">
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
            </>
          )}
        </div>

        {/* Right Panel - Document Viewer */}
        <div className="w-[40%] overflow-y-auto rounded-lg border border-border-subtle bg-surface-raised sticky top-0">
          {!selectedDocId && (
            <div className="flex flex-col items-center justify-center gap-3 py-24">
              <FileText className="h-10 w-10 text-text-disabled" />
              <p className="text-sm text-text-disabled">
                Select a document to view its contents.
              </p>
            </div>
          )}

          {selectedDocId && selectedDocument.isLoading && (
            <LoadingSpinner className="py-24" />
          )}

          {selectedDocId && selectedDocument.isError && (
            <div className="flex flex-col items-center justify-center gap-3 py-12">
              <AlertCircle className="h-8 w-8 text-accent-red" />
              <p className="text-sm text-accent-red">Failed to load document.</p>
            </div>
          )}

          {selectedDocId && selectedDocument.isSuccess && selectedDocument.data && (
            <DocumentViewer document={selectedDocument.data} />
          )}
        </div>
      </div>
    </div>
  );
}

function DocumentViewer({ document: doc }: { document: Document }) {
  return (
    <div className="flex flex-col">
      {/* Metadata Header */}
      <div className="border-b border-border-subtle p-4">
        <div className="flex items-center gap-2 mb-2">
          <Hash className="h-3.5 w-3.5 text-text-tertiary" />
          <span className="text-xs font-mono text-text-tertiary">{doc.eftaNumber}</span>
          <TypeBadge type={doc.documentType} />
          {doc.isRedacted && (
            <span className="inline-flex items-center rounded-sm border border-accent-red/30 bg-accent-red/15 px-1.5 py-0.5 text-xs font-medium text-accent-red">
              REDACTED
            </span>
          )}
        </div>

        <h3 className="text-base font-semibold text-text-primary">
          {doc.documentTitle ?? 'Untitled Document'}
        </h3>

        <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
          {doc.documentDate && (
            <div>
              <span className="text-text-tertiary">Date: </span>
              <span className="text-text-secondary">{formatDate(doc.documentDate)}</span>
            </div>
          )}
          {doc.author && (
            <div className="flex items-center gap-1">
              <User className="h-3 w-3 text-text-tertiary" />
              <span className="text-text-tertiary">Author: </span>
              <span className="text-text-secondary">{doc.author}</span>
            </div>
          )}
          {doc.recipient && (
            <div>
              <span className="text-text-tertiary">Recipient: </span>
              <span className="text-text-secondary">{doc.recipient}</span>
            </div>
          )}
          {doc.subject && (
            <div className="col-span-2">
              <span className="text-text-tertiary">Subject: </span>
              <span className="text-text-secondary">{doc.subject}</span>
            </div>
          )}
        </div>

        <div className="mt-3 flex items-center gap-4 text-xs text-text-tertiary">
          {doc.pageCount !== undefined && (
            <span>{doc.pageCount} {doc.pageCount === 1 ? 'page' : 'pages'}</span>
          )}
          {doc.fileSizeBytes !== undefined && (
            <span>{formatFileSize(doc.fileSizeBytes)}</span>
          )}
          {doc.sourceAgency && (
            <span>Source: {doc.sourceAgency}</span>
          )}
          {doc.extractionStatus && (
            <span className="capitalize">Extraction: {doc.extractionStatus}</span>
          )}
        </div>

        {doc.extractionConfidence !== undefined && (
          <div className="mt-2">
            <ConfidenceBadge
              level={
                doc.extractionConfidence >= 0.8
                  ? 'high'
                  : doc.extractionConfidence >= 0.5
                    ? 'medium'
                    : 'low'
              }
            />
          </div>
        )}
      </div>

      {/* Entity Badges */}
      {(doc.author || doc.recipient) && (
        <div className="border-b border-border-subtle p-4">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-text-tertiary mb-2">
            Mentioned Entities
          </h4>
          <div className="flex flex-wrap gap-1">
            {doc.author && (
              <EntityLink
                id={doc.author}
                name={doc.author}
                entityType="person"
              />
            )}
            {doc.recipient && doc.recipient !== doc.author && (
              <EntityLink
                id={doc.recipient}
                name={doc.recipient}
                entityType="person"
              />
            )}
          </div>
        </div>
      )}

      {/* Full Text Content */}
      <div className="p-4">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-text-tertiary mb-3">
          Document Content
        </h4>
        {doc.fullText ? (
          <div className="whitespace-pre-wrap text-sm leading-relaxed text-text-secondary font-mono">
            {doc.fullText}
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center gap-2 py-8">
            <FileText className="h-8 w-8 text-text-disabled" />
            <p className="text-xs text-text-disabled">
              Full text content not available for this document.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
