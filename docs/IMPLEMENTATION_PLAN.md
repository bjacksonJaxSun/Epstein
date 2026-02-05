# Investigative Dashboard - Implementation Plan

**Created:** 2026-02-03
**Status:** Active

---

## Phase 1: Project Scaffolding & Backend Foundation
*Backend .NET solution + React project initialization*

### Step 1.1 - Create backend solution structure
- Create `dashboard/backend/` directory
- Create `EpsteinDashboard.sln` with 4 projects:
  - `EpsteinDashboard.Core` (class library)
  - `EpsteinDashboard.Application` (class library)
  - `EpsteinDashboard.Infrastructure` (class library)
  - `EpsteinDashboard.Api` (ASP.NET Core Web API)
- Set up project references (Clean Architecture)
- Add NuGet packages per Technical PRD Section 3.1

### Step 1.2 - Create domain entities (Core layer)
- Create all 17 entity classes mapping to SQLite schema
- Map snake_case columns to PascalCase properties
- Add navigation properties for foreign key relationships
- Create enums: ConfidenceLevel, MediaType, ExtractionStatus
- Create models: SearchRequest, SearchResult, NetworkNode, NetworkEdge, TimelineEntry, FinancialFlow, PagedResult

### Step 1.3 - Create repository interfaces (Core layer)
- IDocumentRepository, IPersonRepository, IOrganizationRepository
- ILocationRepository, IEventRepository, IRelationshipRepository
- ICommunicationRepository, IFinancialTransactionRepository
- IMediaRepository, IEvidenceRepository
- ISearchService, IGraphQueryService, IExportService

### Step 1.4 - Create Infrastructure data layer
- EpsteinDbContext with all 17 DbSets
- Entity configurations (IEntityTypeConfiguration) for all tables
- Configure WAL mode and connection string to existing SQLite DB
- Repository implementations for all interfaces
- FTS5 virtual table creation + Dapper search provider

### Step 1.5 - Create Application service layer
- DTOs for all entities (DocumentDto, PersonDto, etc.)
- AutoMapper profiles for entity-to-DTO mapping
- Core services: SearchService, TimelineService, NetworkAnalysisService, FinancialAnalysisService
- FluentValidation validators

### Step 1.6 - Create API controllers + Program.cs
- REST controllers: Documents, People, Organizations, Locations, Events, Relationships, Communications, Financial, Media, Search, Export
- Configure DI, CORS, Swagger, health checks
- SignalR hub skeleton (ExtractionHub)
- Test with Swagger UI against real SQLite database

---

## Phase 2: Frontend Scaffolding & Layout
*React + TypeScript project with dark theme shell*

### Step 2.1 - Initialize React project
- Create `dashboard/frontend/` with Vite + React + TypeScript
- Install dependencies: tailwind, shadcn/ui, lucide-react, react-router, zustand, tanstack-query, date-fns, sonner
- Configure Vite proxy to backend API (localhost:5000)
- Set up Tailwind with dark theme design tokens from UX PRD Section 4

### Step 2.2 - Build application shell layout
- DashboardLayout component (sidebar + header + content area)
- Sidebar icon rail (64px, expands to 240px) with all 15 nav items
- Header with global search bar, pins button, help
- React Router setup with all routes
- Right-side context panel (slide-out, 400px)

### Step 2.3 - Create shared components + API client
- API client (fetch wrapper + base URL config)
- TanStack Query provider setup
- Shared components: DataTable, FilterBar, ConfidenceBadge, EntityLink, LoadingSpinner, ErrorBoundary
- Zustand stores: useFilterStore, useSelectionStore, useBoardStore
- TypeScript types for all API response shapes

---

## Phase 3: Core Data Views
*People, Documents, and Overview Dashboard*

### Step 3.1 - Overview Dashboard page
- Statistics cards (total people, documents, events, transactions, locations)
- Most-connected people list (top 10 by relationship count)
- Recent events feed
- Financial summary card
- Quick action buttons to navigate to views

### Step 3.2 - People directory + detail page
- PeoplePage: searchable, sortable data table with virtual scrolling
- PersonDetailPage: tabbed profile (Overview, Relationships, Events, Documents, Financial, Communications, Media, Notes)
- People API hooks (usePeople, usePersonDetail)
- Entity link click -> context panel slide-in

### Step 3.3 - Document viewer
- DocumentsPage: filterable document list with search
- DocumentViewer: full-text display with entity highlighting
- Full-text search integration (FTS5 endpoint)
- Search results with highlighted snippets

### Step 3.4 - Organizations, Locations, Communications, Evidence pages
- Basic list + detail views for remaining entity types
- Reuse DataTable and FilterBar patterns
- Wire up to respective API endpoints

---

## Phase 4: Visualization Views
*Network graph, timeline, financial flows, map*

### Step 4.1 - Network graph (Cytoscape.js)
- Install cytoscape + layout extensions (cola, fcose)
- NetworkGraph component with force-directed layout
- Node types: person (circle), organization (diamond), location (square)
- Edge encoding by relationship type (color) and confidence (opacity)
- Click node -> context panel; double-click -> re-center graph
- Controls: zoom, fit, layout toggle, depth selector
- Find-path feature between two selected nodes

### Step 4.2 - Event timeline (vis-timeline)
- Install vis-timeline + vis-data
- EventTimeline component with zoom/pan, date range selection
- Swimlanes grouped by event type
- Timeline items colored by event type
- Click event -> context panel with full details
- Filter by person, event type, date range
- Brush selection to filter other views

### Step 4.3 - Financial flow (d3-sankey)
- SankeyDiagram component showing money flow between parties
- Aggregate transactions by source/target
- Color-code by transaction volume
- TransactionTable below with sortable columns
- FinancialSummary card with totals, currency breakdown
- Anomaly highlighting on unusual patterns

### Step 4.4 - Map view (MapLibre GL)
- Install react-map-gl + maplibre-gl
- LocationMap with dark tile layer (CartoDB dark matter)
- Clustered markers for locations
- Click marker -> popup with location details + linked events
- Heatmap layer for event density
- Filter by location type, date range

---

## Phase 5: Search, Investigation & AI Features

### Step 5.1 - Global search system
- Universal search component in header
- Categorized dropdown results (People, Orgs, Docs, Events, Locations)
- Debounced search (200ms)
- Keyboard navigation (arrows, enter, escape)
- Recent searches
- Full search results page with filters

### Step 5.2 - Investigation boards
- InvestigationBoard: infinite canvas with drag-and-drop (@dnd-kit)
- BoardCard: entity cards pinnable from any view
- BoardConnection: draw lines between cards
- BoardToolbar: add note, screenshot, export
- Persist boards to localStorage (or companion SQLite table)
- Multiple named boards

### Step 5.3 - Bookmarks and annotations
- Pin/bookmark any entity from anywhere
- BookmarksPage: organized by entity type
- Annotation system: add notes, tags, status flags to any entity
- Persist to localStorage

### Step 5.4 - AI analysis integration
- AnalysisController integration (entity extraction, connection suggestions, pattern detection)
- AI Insights page showing all detected patterns
- "Analyze" button on document/person detail pages
- Progress indicator during AI processing (SignalR)
- Display confidence scores on AI-generated insights

---

## Phase 6: Polish & Deployment

### Step 6.1 - Cross-view interaction
- Click any entity anywhere -> context panel
- Linked brushing: selecting items in one view highlights in others
- Keyboard shortcuts (Ctrl+K search, Ctrl+B boards, Escape close panel)
- Breadcrumb navigation

### Step 6.2 - Export functionality
- CSV export for filtered data tables
- JSON export for graph data
- PDF report generation
- GEXF/GraphML network export

### Step 6.3 - Docker deployment
- Backend Dockerfile (multi-stage .NET build)
- Frontend Dockerfile (Vite build + Nginx serve)
- docker-compose.yml with nginx reverse proxy
- Volume mounts for SQLite DB and document files
- Environment variable configuration
- Health check endpoints

---

## Implementation Order

| Step | Dependencies | Status |
|------|-------------|--------|
| 1.1 | None | Pending |
| 1.2 | 1.1 | Pending |
| 1.3 | 1.2 | Pending |
| 1.4 | 1.2, 1.3 | Pending |
| 1.5 | 1.2, 1.3 | Pending |
| 1.6 | 1.4, 1.5 | Pending |
| 2.1 | None (parallel with Phase 1) | Pending |
| 2.2 | 2.1 | Pending |
| 2.3 | 2.1 | Pending |
| 3.1 | 1.6, 2.2, 2.3 | Pending |
| 3.2 | 3.1 | Pending |
| 3.3 | 3.1 | Pending |
| 3.4 | 3.1 | Pending |
| 4.1 | 3.1 | Pending |
| 4.2 | 3.1 | Pending |
| 4.3 | 3.1 | Pending |
| 4.4 | 3.1 | Pending |
| 5.1 | 3.1 | Pending |
| 5.2 | 3.1 | Pending |
| 5.3 | 5.2 | Pending |
| 5.4 | 1.6, 3.1 | Pending |
| 6.1 | Phase 3, Phase 4 | Pending |
| 6.2 | Phase 3 | Pending |
| 6.3 | All | Pending |
