# Investigative Document Analysis Dashboard - Technical PRD

**Version:** 1.0
**Last Updated:** 2026-02-03
**Author:** Software Architect
**Status:** Draft

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Architecture](#2-system-architecture)
3. [Technology Stack](#3-technology-stack)
4. [Project Structure](#4-project-structure)
5. [Data Access Layer Design](#5-data-access-layer-design)
6. [API Contract Specifications](#6-api-contract-specifications)
7. [Frontend Component Architecture](#7-frontend-component-architecture)
8. [State Management Approach](#8-state-management-approach)
9. [AI Integration Architecture](#9-ai-integration-architecture)
10. [Performance Considerations](#10-performance-considerations)
11. [Security Architecture](#11-security-architecture)
12. [Docker Deployment Configuration](#12-docker-deployment-configuration)
13. [Development Environment Setup](#13-development-environment-setup)
14. [Build and Deployment Pipeline](#14-build-and-deployment-pipeline)
15. [AI API Cost Estimates](#15-ai-api-cost-estimates)
16. [Risk Assessment and Mitigations](#16-risk-assessment-and-mitigations)
17. [Appendix A: Database Schema Reference](#appendix-a-database-schema-reference)
18. [Appendix B: API Response Schemas](#appendix-b-api-response-schemas)

---

## 1. Executive Summary

### 1.1 Purpose

This document specifies the technical architecture for an investigative document analysis dashboard. The system provides a comprehensive single-page application for exploring, visualizing, and analyzing extracted document data stored in an existing SQLite database (17 tables). The dashboard integrates interactive timeline visualization, network graph exploration, financial flow analysis, full-text search, media analysis, geospatial mapping, and AI-assisted investigation workflows.

### 1.2 Scope

The system is self-hosted (Docker Compose), operates in read-write mode against the existing SQLite database at `extraction_output/epstein_documents.db`, and provides a React + TypeScript SPA frontend served by an ASP.NET Core Web API backend. AI integration uses a multi-provider architecture (OpenAI, Claude) consistent with the existing JaxSun.Ideas platform patterns.

### 1.3 Key Design Decisions

| Decision | Rationale |
|---|---|
| **React SPA over Blazor** | Visualization library ecosystem (d3, cytoscape, vis.js) is vastly richer in the JavaScript/TypeScript world. Blazor interop overhead for these libraries is non-trivial and introduces fragility. |
| **Separate backend project** | The dashboard operates on a fundamentally different database schema (17-table document analysis) than the Ideas platform (50+ table business platform). Sharing a DbContext would couple unrelated domains. |
| **SQLite retained** | The existing extraction pipeline writes to SQLite. Adding PostgreSQL introduces operational complexity without clear benefit for a self-hosted, single-user investigative tool. SQLite handles concurrent reads well and the write volume is low. |
| **HotChocolate GraphQL alongside REST** | Relationship traversal queries (e.g., "find all people connected to Person X within 3 hops who attended events at Location Y") are naturally expressed in GraphQL. REST remains for simple CRUD and bulk operations. |
| **Zustand over Redux** | Minimal boilerplate, TypeScript-first, and sufficient for the dashboard's state complexity. No middleware chain needed. |

---

## 2. System Architecture

### 2.1 High-Level Architecture Diagram

```
+------------------------------------------------------------------+
|                        Docker Compose Host                        |
|                                                                   |
|  +-------------------------------------------------------------+ |
|  |                    Nginx Reverse Proxy                       | |
|  |            (TLS termination, static file serving)            | |
|  |  Port 443 (HTTPS) / Port 80 (HTTP redirect)                 | |
|  +-----+-------------------------------------------+-----------+ |
|        |                                           |              |
|        | /api/*, /graphql, /ws                      | /*           |
|        v                                           v              |
|  +-------------------------+    +----------------------------------+
|  |  ASP.NET Core Web API   |    |     React SPA (Static Build)    |
|  |  (.NET 9, Kestrel)      |    |     Served by Nginx             |
|  |  Port 5000 (internal)   |    |     (Vite production build)     |
|  |                         |    +----------------------------------+
|  |  +-------------------+  |                                      |
|  |  | REST Controllers  |  |                                      |
|  |  +-------------------+  |                                      |
|  |  | GraphQL Endpoint  |  |                                      |
|  |  | (HotChocolate)    |  |                                      |
|  |  +-------------------+  |                                      |
|  |  | WebSocket Hub     |  |                                      |
|  |  | (SignalR)         |  |                                      |
|  |  +-------------------+  |                                      |
|  |  | AI Service Layer  |  |                                      |
|  |  +-------------------+  |                                      |
|  |  | Data Access Layer |  |                                      |
|  |  | (EF Core + Dapper)|  |                                      |
|  |  +--------+----------+  |                                      |
|  +-----------|-------------+                                      |
|              |                                                    |
|              v                                                    |
|  +--------------------------+   +------------------------------+  |
|  |   SQLite Database        |   |  Document File Store         |  |
|  |   epstein_documents.db   |   |  (Volume-mounted PDFs,      |  |
|  |   (Volume-mounted)       |   |   images from extraction)   |  |
|  +--------------------------+   +------------------------------+  |
|                                                                   |
+------------------------------------------------------------------+
         |                             |
         v                             v
  +---------------+           +------------------+
  | OpenAI API    |           | Anthropic API    |
  | (gpt-4o)      |           | (claude-sonnet)  |
  +---------------+           +------------------+
```

### 2.2 Component Interaction Flow

```
                          User Browser
                               |
                    +----------+----------+
                    |                     |
               React SPA            WebSocket
            (REST/GraphQL)         (SignalR Hub)
                    |                     |
                    v                     v
            +-------+-------+    +-------+-------+
            |  API Gateway  |    | Notification  |
            | (Controllers) |    | Hub           |
            +-------+-------+    +-------+-------+
                    |                     |
        +-----------+-----------+         |
        |           |           |         |
   +----+----+ +----+----+ +---+---+     |
   |  Query  | | Command | | Search|     |
   | Service | | Service | | Svc   |     |
   +----+----+ +----+----+ +---+---+     |
        |           |           |         |
        +-----+-----+-----+----+---------+
              |           |
        +-----+-----+ +---+----------+
        | EF Core   | | Dapper       |
        | (CRUD,    | | (FTS5, bulk  |
        |  graphs)  | |  queries,    |
        |           | |  aggregates) |
        +-----+-----+ +---+----------+
              |            |
              +------+-----+
                     |
              +------+------+
              |   SQLite    |
              |   Database  |
              +-------------+
```

### 2.3 Data Flow Architecture

```
+------------------+     +-----------------+     +------------------+
|  Extraction      |     |  Dashboard API  |     |  Dashboard UI    |
|  Pipeline        |     |  (Read/Write)   |     |  (React SPA)     |
|  (Python)        |     |                 |     |                  |
|                  |     |  Entity CRUD    |<--->|  Data Grids      |
|  PDF Extraction -+---->|  FTS5 Search    |<--->|  Network Graph   |
|  NER Processing  |     |  Graph Queries  |<--->|  Timeline        |
|  Image Analysis  |     |  AI Analysis    |<--->|  Sankey Diagram  |
|  Relationship    |     |  Export         |<--->|  Map View        |
|  Building        |     |  WebSocket      |<--->|  Media Gallery   |
+------------------+     +-----------------+     +------------------+
        |                        |
        v                        v
+------------------+     +-----------------+
| SQLite DB        |     | AI Providers    |
| (shared volume)  |     | OpenAI / Claude |
+------------------+     +-----------------+
```

---

## 3. Technology Stack

### 3.1 Backend

| Component | Technology | Version | Justification |
|---|---|---|---|
| **Runtime** | .NET 9 | 9.0.x | Consistent with JaxSun.Ideas platform; latest LTS-adjacent release with performance improvements |
| **Web Framework** | ASP.NET Core | 9.0.x | Mature, performant, cross-platform; Docker-ready |
| **ORM (Primary)** | Entity Framework Core | 9.0.x | Strongly-typed CRUD operations, change tracking, migrations for schema evolution |
| **ORM (Performance)** | Dapper | 2.1.x | Raw SQL for FTS5 queries, bulk aggregations, complex joins where EF overhead is unwarranted |
| **SQLite Provider** | Microsoft.EntityFrameworkCore.Sqlite | 9.0.x | First-party SQLite support for EF Core |
| **GraphQL** | HotChocolate | 15.1.x | Best .NET GraphQL server; code-first schema, filtering, sorting, paging, projections out of the box |
| **Real-time** | SignalR | 9.0.x (built-in) | WebSocket abstraction for extraction progress, live updates |
| **Logging** | Serilog | 4.2.x | Structured logging consistent with existing platform |
| **Validation** | FluentValidation | 11.11.x | Consistent with existing platform patterns |
| **Mapping** | AutoMapper | 12.0.x | DTO mapping consistent with existing platform |
| **API Documentation** | Swashbuckle (Swagger) | 7.x | OpenAPI 3.0 spec generation |
| **Health Checks** | Microsoft.Extensions.Diagnostics.HealthChecks | 9.0.x | Container orchestration readiness/liveness probes |

### 3.2 Frontend

| Component | Technology | Version | Justification |
|---|---|---|---|
| **Framework** | React | 19.2.x | Latest stable; Server Components not needed (SPA), but hooks and concurrent features used |
| **Language** | TypeScript | 5.7.x | Type safety, IDE support, refactoring confidence |
| **Build Tool** | Vite | 7.3.x | Sub-second HMR, Rolldown-powered production builds, tree-shaking |
| **State Management** | Zustand | 5.0.x | Minimal boilerplate, TypeScript-first, middleware support (persist, devtools) |
| **Server State** | TanStack React Query | 5.90.x | Cache management, background refetching, optimistic updates, infinite scroll |
| **Routing** | React Router | 7.x | File-based routing support, nested layouts |
| **Network Graph** | Cytoscape.js | 3.33.x | Most capable graph library; layout algorithms (cola, dagre, fcose), event handling, styling, extensions ecosystem. Preferred over vis-network for complex investigative graph traversal and compound nodes |
| **Timeline** | vis-timeline | 8.5.x | Purpose-built timeline visualization with zoom, pan, grouping, and range selection |
| **Financial Diagrams** | d3-sankey | 0.12.x | Standard Sankey diagram implementation; combined with d3-selection for React integration |
| **D3 Core** | d3 (modular) | 7.x | d3-selection, d3-scale, d3-axis, d3-shape for custom charts |
| **Maps** | react-map-gl + MapLibre GL JS | 8.1.x / 5.x | Vector tile rendering, smooth WebGL performance, open-source (no Mapbox token required with OpenFreeMap tiles) |
| **Virtual Scrolling** | TanStack Virtual | 3.13.x | Headless virtualizer for document lists, search results; 60fps scrolling for 100K+ rows |
| **Data Grid** | TanStack Table | 8.x | Headless table with sorting, filtering, grouping, column pinning, virtualized rendering |
| **Drag and Drop** | @dnd-kit/core | 6.x | Accessible drag-and-drop for investigation board; keyboard support, collision detection |
| **PDF Viewer** | react-pdf | 9.x | Client-side PDF rendering with page-level controls |
| **UI Components** | shadcn/ui + Tailwind CSS | latest / 3.x | Copy-paste components (not a dependency), Radix UI primitives, consistent design system |
| **Icons** | Lucide React | 0.475.x | Tree-shakeable icon library |
| **HTTP Client** | Built-in fetch + TanStack Query | -- | No axios needed; Query handles retries, caching, deduplication |
| **GraphQL Client** | graphql-request | 7.x | Minimal GraphQL client; pairs with TanStack Query for caching |
| **WebSocket** | @microsoft/signalr | 9.0.x | Official SignalR JavaScript client |
| **Date Handling** | date-fns | 4.x | Tree-shakeable, immutable date operations |
| **Toast/Notifications** | sonner | 2.x | Lightweight, accessible toast notifications |

### 3.3 Infrastructure

| Component | Technology | Version | Justification |
|---|---|---|---|
| **Containerization** | Docker | 27.x | Standard container runtime |
| **Orchestration** | Docker Compose | 2.x | Single-host multi-container orchestration |
| **Reverse Proxy** | Nginx | 1.27.x | TLS termination, static file serving, API proxying, gzip/brotli compression |
| **CI/CD** | GitHub Actions | -- | Build, test, publish Docker images |

---

## 4. Project Structure

### 4.1 Repository Layout

```
EpsteinDownloader/
+-- docs/
|   +-- DASHBOARD_TECHNICAL_PRD.md        # This document
|   +-- API_REFERENCE.md                  # Generated OpenAPI reference
|
+-- dashboard/                            # Dashboard monorepo root
|   +-- docker-compose.yml                # Full stack deployment
|   +-- docker-compose.dev.yml            # Development overrides
|   +-- .env.example                      # Environment template
|   +-- nginx/
|   |   +-- nginx.conf                    # Reverse proxy configuration
|   |   +-- ssl/                          # TLS certificates (gitignored)
|   |
|   +-- backend/                          # ASP.NET Core Web API
|   |   +-- src/
|   |   |   +-- EpsteinDashboard.Api/             # API host project
|   |   |   |   +-- Controllers/
|   |   |   |   |   +-- DocumentsController.cs
|   |   |   |   |   +-- PeopleController.cs
|   |   |   |   |   +-- OrganizationsController.cs
|   |   |   |   |   +-- LocationsController.cs
|   |   |   |   |   +-- EventsController.cs
|   |   |   |   |   +-- RelationshipsController.cs
|   |   |   |   |   +-- CommunicationsController.cs
|   |   |   |   |   +-- FinancialController.cs
|   |   |   |   |   +-- MediaController.cs
|   |   |   |   |   +-- SearchController.cs
|   |   |   |   |   +-- ExportController.cs
|   |   |   |   |   +-- AnalysisController.cs
|   |   |   |   +-- GraphQL/
|   |   |   |   |   +-- Query.cs
|   |   |   |   |   +-- Mutation.cs
|   |   |   |   |   +-- Types/
|   |   |   |   |   |   +-- PersonType.cs
|   |   |   |   |   |   +-- DocumentType.cs
|   |   |   |   |   |   +-- RelationshipType.cs
|   |   |   |   |   |   +-- EventType.cs
|   |   |   |   |   |   +-- ...
|   |   |   |   |   +-- Filters/
|   |   |   |   |   +-- Sorting/
|   |   |   |   +-- Hubs/
|   |   |   |   |   +-- ExtractionHub.cs
|   |   |   |   |   +-- AnalysisHub.cs
|   |   |   |   +-- Program.cs
|   |   |   |   +-- appsettings.json
|   |   |   |   +-- appsettings.Development.json
|   |   |   |   +-- Dockerfile
|   |   |   |   +-- EpsteinDashboard.Api.csproj
|   |   |   |
|   |   |   +-- EpsteinDashboard.Core/              # Domain layer
|   |   |   |   +-- Entities/
|   |   |   |   |   +-- Document.cs
|   |   |   |   |   +-- Person.cs
|   |   |   |   |   +-- Organization.cs
|   |   |   |   |   +-- Location.cs
|   |   |   |   |   +-- Event.cs
|   |   |   |   |   +-- Relationship.cs
|   |   |   |   |   +-- EventParticipant.cs
|   |   |   |   |   +-- Communication.cs
|   |   |   |   |   +-- CommunicationRecipient.cs
|   |   |   |   |   +-- FinancialTransaction.cs
|   |   |   |   |   +-- EvidenceItem.cs
|   |   |   |   |   +-- MediaFile.cs
|   |   |   |   |   +-- ImageAnalysis.cs
|   |   |   |   |   +-- VisualEntity.cs
|   |   |   |   |   +-- MediaPerson.cs
|   |   |   |   |   +-- MediaEvent.cs
|   |   |   |   |   +-- ExtractionLog.cs
|   |   |   |   +-- Interfaces/
|   |   |   |   |   +-- IDocumentRepository.cs
|   |   |   |   |   +-- IPersonRepository.cs
|   |   |   |   |   +-- IRelationshipRepository.cs
|   |   |   |   |   +-- ISearchService.cs
|   |   |   |   |   +-- IAIAnalysisService.cs
|   |   |   |   |   +-- IGraphQueryService.cs
|   |   |   |   |   +-- IExportService.cs
|   |   |   |   +-- Enums/
|   |   |   |   |   +-- ConfidenceLevel.cs
|   |   |   |   |   +-- DocumentType.cs
|   |   |   |   |   +-- RelationshipType.cs
|   |   |   |   |   +-- MediaType.cs
|   |   |   |   |   +-- ExtractionStatus.cs
|   |   |   |   +-- Models/
|   |   |   |   |   +-- SearchRequest.cs
|   |   |   |   |   +-- SearchResult.cs
|   |   |   |   |   +-- GraphTraversal.cs
|   |   |   |   |   +-- TimelineEntry.cs
|   |   |   |   |   +-- FinancialFlow.cs
|   |   |   |   |   +-- NetworkNode.cs
|   |   |   |   |   +-- NetworkEdge.cs
|   |   |   |   +-- EpsteinDashboard.Core.csproj
|   |   |   |
|   |   |   +-- EpsteinDashboard.Application/       # Business logic
|   |   |   |   +-- Services/
|   |   |   |   |   +-- SearchService.cs
|   |   |   |   |   +-- GraphQueryService.cs
|   |   |   |   |   +-- TimelineService.cs
|   |   |   |   |   +-- NetworkAnalysisService.cs
|   |   |   |   |   +-- FinancialAnalysisService.cs
|   |   |   |   |   +-- ExportService.cs
|   |   |   |   |   +-- MediaAnalysisService.cs
|   |   |   |   +-- AI/
|   |   |   |   |   +-- EntityExtractionService.cs
|   |   |   |   |   +-- ConnectionSuggestionService.cs
|   |   |   |   |   +-- PatternDetectionService.cs
|   |   |   |   |   +-- AnomalyDetectionService.cs
|   |   |   |   |   +-- DocumentSummarizationService.cs
|   |   |   |   +-- DTOs/
|   |   |   |   |   +-- DocumentDto.cs
|   |   |   |   |   +-- PersonDto.cs
|   |   |   |   |   +-- TimelineDto.cs
|   |   |   |   |   +-- NetworkGraphDto.cs
|   |   |   |   |   +-- SankeyDto.cs
|   |   |   |   |   +-- SearchResultDto.cs
|   |   |   |   |   +-- ...
|   |   |   |   +-- Mappings/
|   |   |   |   |   +-- DocumentProfile.cs
|   |   |   |   |   +-- PersonProfile.cs
|   |   |   |   |   +-- ...
|   |   |   |   +-- Validators/
|   |   |   |   +-- EpsteinDashboard.Application.csproj
|   |   |   |
|   |   |   +-- EpsteinDashboard.Infrastructure/     # Data access
|   |   |   |   +-- Data/
|   |   |   |   |   +-- EpsteinDbContext.cs
|   |   |   |   |   +-- Configurations/
|   |   |   |   |   |   +-- DocumentConfiguration.cs
|   |   |   |   |   |   +-- PersonConfiguration.cs
|   |   |   |   |   |   +-- ...
|   |   |   |   |   +-- Repositories/
|   |   |   |   |   |   +-- DocumentRepository.cs
|   |   |   |   |   |   +-- PersonRepository.cs
|   |   |   |   |   |   +-- RelationshipRepository.cs
|   |   |   |   |   |   +-- ...
|   |   |   |   +-- Search/
|   |   |   |   |   +-- Fts5SearchProvider.cs
|   |   |   |   |   +-- Fts5VirtualTableManager.cs
|   |   |   |   +-- AI/
|   |   |   |   |   +-- OpenAIProvider.cs
|   |   |   |   |   +-- ClaudeProvider.cs
|   |   |   |   |   +-- AIProviderFactory.cs
|   |   |   |   +-- Export/
|   |   |   |   |   +-- CsvExporter.cs
|   |   |   |   |   +-- JsonExporter.cs
|   |   |   |   |   +-- PdfReportGenerator.cs
|   |   |   |   +-- DependencyInjection.cs
|   |   |   |   +-- EpsteinDashboard.Infrastructure.csproj
|   |   |   |
|   |   |   +-- EpsteinDashboard.sln
|   |   |
|   |   +-- tests/
|   |       +-- EpsteinDashboard.Core.Tests/
|   |       +-- EpsteinDashboard.Application.Tests/
|   |       +-- EpsteinDashboard.Infrastructure.Tests/
|   |       +-- EpsteinDashboard.Api.Tests/
|   |
|   +-- frontend/                          # React SPA
|       +-- src/
|       |   +-- main.tsx                   # App entry point
|       |   +-- App.tsx                    # Root component + router
|       |   +-- vite-env.d.ts
|       |   +-- index.css                  # Tailwind imports
|       |   +-- api/
|       |   |   +-- client.ts             # Base fetch wrapper
|       |   |   +-- graphql.ts            # GraphQL client setup
|       |   |   +-- signalr.ts            # SignalR connection
|       |   |   +-- endpoints/
|       |   |       +-- documents.ts
|       |   |       +-- people.ts
|       |   |       +-- search.ts
|       |   |       +-- analysis.ts
|       |   |       +-- ...
|       |   +-- stores/
|       |   |   +-- useFilterStore.ts      # Global filter state
|       |   |   +-- useSelectionStore.ts   # Selection state
|       |   |   +-- useBoardStore.ts       # Investigation board
|       |   |   +-- useNotificationStore.ts
|       |   +-- hooks/
|       |   |   +-- useDocuments.ts
|       |   |   +-- usePeople.ts
|       |   |   +-- useSearch.ts
|       |   |   +-- useTimeline.ts
|       |   |   +-- useNetwork.ts
|       |   |   +-- useFinancials.ts
|       |   |   +-- useSignalR.ts
|       |   |   +-- useVirtualScroll.ts
|       |   +-- components/
|       |   |   +-- layout/
|       |   |   |   +-- DashboardLayout.tsx
|       |   |   |   +-- Sidebar.tsx
|       |   |   |   +-- Header.tsx
|       |   |   |   +-- PanelGroup.tsx
|       |   |   +-- timeline/
|       |   |   |   +-- EventTimeline.tsx
|       |   |   |   +-- TimelineControls.tsx
|       |   |   |   +-- TimelineTooltip.tsx
|       |   |   +-- network/
|       |   |   |   +-- NetworkGraph.tsx
|       |   |   |   +-- NetworkControls.tsx
|       |   |   |   +-- NodeDetail.tsx
|       |   |   |   +-- EdgeDetail.tsx
|       |   |   +-- financial/
|       |   |   |   +-- SankeyDiagram.tsx
|       |   |   |   +-- TransactionTable.tsx
|       |   |   |   +-- FinancialSummary.tsx
|       |   |   +-- documents/
|       |   |   |   +-- DocumentList.tsx
|       |   |   |   +-- DocumentViewer.tsx
|       |   |   |   +-- DocumentSearch.tsx
|       |   |   |   +-- SearchResults.tsx
|       |   |   +-- media/
|       |   |   |   +-- MediaGallery.tsx
|       |   |   |   +-- MediaViewer.tsx
|       |   |   |   +-- AIAnalysisOverlay.tsx
|       |   |   |   +-- FaceDetectionOverlay.tsx
|       |   |   +-- map/
|       |   |   |   +-- LocationMap.tsx
|       |   |   |   +-- MapControls.tsx
|       |   |   |   +-- LocationCluster.tsx
|       |   |   +-- board/
|       |   |   |   +-- InvestigationBoard.tsx
|       |   |   |   +-- BoardCard.tsx
|       |   |   |   +-- BoardConnection.tsx
|       |   |   |   +-- BoardToolbar.tsx
|       |   |   +-- shared/
|       |   |       +-- DataTable.tsx
|       |   |       +-- FilterBar.tsx
|       |   |       +-- ConfidenceBadge.tsx
|       |   |       +-- EntityLink.tsx
|       |   |       +-- LoadingSpinner.tsx
|       |   |       +-- ErrorBoundary.tsx
|       |   +-- pages/
|       |   |   +-- DashboardPage.tsx
|       |   |   +-- DocumentsPage.tsx
|       |   |   +-- PeoplePage.tsx
|       |   |   +-- PersonDetailPage.tsx
|       |   |   +-- NetworkPage.tsx
|       |   |   +-- TimelinePage.tsx
|       |   |   +-- FinancialPage.tsx
|       |   |   +-- MediaPage.tsx
|       |   |   +-- MapPage.tsx
|       |   |   +-- InvestigationPage.tsx
|       |   |   +-- SearchPage.tsx
|       |   |   +-- SettingsPage.tsx
|       |   +-- types/
|       |   |   +-- document.ts
|       |   |   +-- person.ts
|       |   |   +-- relationship.ts
|       |   |   +-- event.ts
|       |   |   +-- financial.ts
|       |   |   +-- media.ts
|       |   |   +-- search.ts
|       |   |   +-- api.ts
|       |   +-- utils/
|       |       +-- formatters.ts
|       |       +-- graph-layout.ts
|       |       +-- sankey-transform.ts
|       |       +-- timeline-transform.ts
|       |       +-- debounce.ts
|       +-- public/
|       |   +-- favicon.svg
|       +-- package.json
|       +-- tsconfig.json
|       +-- vite.config.ts
|       +-- tailwind.config.ts
|       +-- postcss.config.js
|       +-- Dockerfile
|       +-- .env.example
```

### 4.2 Solution Dependencies (Backend)

```
EpsteinDashboard.Api
  +-- EpsteinDashboard.Application
  +-- EpsteinDashboard.Infrastructure
  +-- EpsteinDashboard.Core (transitive)

EpsteinDashboard.Application
  +-- EpsteinDashboard.Core

EpsteinDashboard.Infrastructure
  +-- EpsteinDashboard.Core
  +-- EpsteinDashboard.Application
```

Clean Architecture layer rules:
- **Core** has zero project references (domain entities, interfaces, models, enums only)
- **Application** references Core only (services, DTOs, validators, mappings)
- **Infrastructure** references Core and Application (EF Core, Dapper, AI providers, exporters)
- **Api** references Application and Infrastructure (controllers, GraphQL, hubs, DI composition)

---

## 5. Data Access Layer Design

### 5.1 Dual ORM Strategy

The data access layer uses two ORMs for different purposes.

**Entity Framework Core** handles:
- CRUD operations on all 17 tables
- Navigation property loading (relationships, event participants, media links)
- Change tracking for write operations
- Schema validation at startup (model-to-database comparison)

**Dapper** handles:
- FTS5 full-text search queries (EF Core has no native FTS5 support)
- Complex aggregation queries (e.g., financial totals by person, event counts by time period)
- Bulk read operations where EF tracking overhead is unwarranted
- Custom graph traversal queries (shortest path, N-hop neighbors)

### 5.2 EF Core DbContext Design

```csharp
public class EpsteinDbContext : DbContext
{
    // Core tables
    public DbSet<Document> Documents => Set<Document>();
    public DbSet<Person> People => Set<Person>();
    public DbSet<Organization> Organizations => Set<Organization>();
    public DbSet<Location> Locations => Set<Location>();
    public DbSet<Event> Events => Set<Event>();

    // Relationship tables
    public DbSet<Relationship> Relationships => Set<Relationship>();
    public DbSet<EventParticipant> EventParticipants => Set<EventParticipant>();

    // Communications
    public DbSet<Communication> Communications => Set<Communication>();
    public DbSet<CommunicationRecipient> CommunicationRecipients
        => Set<CommunicationRecipient>();

    // Financial
    public DbSet<FinancialTransaction> FinancialTransactions
        => Set<FinancialTransaction>();

    // Evidence
    public DbSet<EvidenceItem> EvidenceItems => Set<EvidenceItem>();

    // Media pipeline
    public DbSet<MediaFile> MediaFiles => Set<MediaFile>();
    public DbSet<ImageAnalysis> ImageAnalyses => Set<ImageAnalysis>();
    public DbSet<VisualEntity> VisualEntities => Set<VisualEntity>();
    public DbSet<MediaPerson> MediaPeople => Set<MediaPerson>();
    public DbSet<MediaEvent> MediaEvents => Set<MediaEvent>();

    // Extraction tracking
    public DbSet<ExtractionLog> ExtractionLogs => Set<ExtractionLog>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        base.OnModelCreating(modelBuilder);
        modelBuilder.ApplyConfigurationsFromAssembly(
            typeof(EpsteinDbContext).Assembly);
    }
}
```

### 5.3 Entity Configuration Example

```csharp
public class PersonConfiguration : IEntityTypeConfiguration<Person>
{
    public void Configure(EntityTypeBuilder<Person> builder)
    {
        builder.ToTable("people");
        builder.HasKey(p => p.PersonId);
        builder.Property(p => p.PersonId).HasColumnName("person_id");
        builder.Property(p => p.FullName).HasColumnName("full_name")
            .HasMaxLength(255).IsRequired();
        builder.Property(p => p.NameVariations).HasColumnName("name_variations")
            .HasColumnType("TEXT"); // JSON array in SQLite
        builder.Property(p => p.PrimaryRole).HasColumnName("primary_role")
            .HasMaxLength(100);
        builder.Property(p => p.ConfidenceLevel).HasColumnName("confidence_level")
            .HasMaxLength(50).HasDefaultValue("medium");

        // Navigation properties
        builder.HasMany(p => p.RelationshipsFrom)
            .WithOne(r => r.Person1)
            .HasForeignKey(r => r.Person1Id);
        builder.HasMany(p => p.RelationshipsTo)
            .WithOne(r => r.Person2)
            .HasForeignKey(r => r.Person2Id);
        builder.HasMany(p => p.EventParticipations)
            .WithOne(ep => ep.Person)
            .HasForeignKey(ep => ep.PersonId);
        builder.HasMany(p => p.MediaAppearances)
            .WithOne(mp => mp.Person)
            .HasForeignKey(mp => mp.PersonId);
    }
}
```

### 5.4 FTS5 Full-Text Search Integration

Since EF Core lacks native FTS5 support, the search layer uses Dapper with raw SQL against a virtual table that shadows the `documents` table.

**FTS5 Virtual Table (created via raw migration):**

```sql
-- Created during application startup if not exists
CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
    document_title,
    full_text,
    subject,
    author,
    content='documents',
    content_rowid='document_id',
    tokenize='porter unicode61'
);

-- Triggers to keep FTS index synchronized
CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents BEGIN
    INSERT INTO documents_fts(rowid, document_title, full_text, subject, author)
    VALUES (new.document_id, new.document_title, new.full_text,
            new.subject, new.author);
END;

CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents BEGIN
    INSERT INTO documents_fts(documents_fts, rowid,
        document_title, full_text, subject, author)
    VALUES('delete', old.document_id, old.document_title, old.full_text,
           old.subject, old.author);
END;

CREATE TRIGGER IF NOT EXISTS documents_au AFTER UPDATE ON documents BEGIN
    INSERT INTO documents_fts(documents_fts, rowid,
        document_title, full_text, subject, author)
    VALUES('delete', old.document_id, old.document_title, old.full_text,
           old.subject, old.author);
    INSERT INTO documents_fts(rowid, document_title, full_text, subject, author)
    VALUES (new.document_id, new.document_title, new.full_text,
            new.subject, new.author);
END;
```

**Dapper Search Query:**

```csharp
public class Fts5SearchProvider : ISearchService
{
    private readonly IDbConnection _connection;

    public async Task<SearchResultPage> SearchAsync(
        SearchRequest request,
        CancellationToken ct = default)
    {
        var sql = @"
            SELECT
                d.document_id,
                d.efta_number,
                d.document_title,
                d.document_type,
                d.document_date,
                highlight(documents_fts, 1, '<mark>', '</mark>') AS snippet,
                rank
            FROM documents_fts
            INNER JOIN documents d ON d.document_id = documents_fts.rowid
            WHERE documents_fts MATCH @Query
            ORDER BY rank
            LIMIT @PageSize OFFSET @Offset";

        var results = await _connection.QueryAsync<SearchResultDto>(
            sql,
            new {
                Query = SanitizeFts5Query(request.Query),
                PageSize = request.PageSize,
                Offset = request.Page * request.PageSize
            });

        var countSql = @"
            SELECT COUNT(*)
            FROM documents_fts
            WHERE documents_fts MATCH @Query";

        var totalCount = await _connection.ExecuteScalarAsync<int>(
            countSql,
            new { Query = SanitizeFts5Query(request.Query) });

        return new SearchResultPage
        {
            Results = results.ToList(),
            TotalCount = totalCount,
            Page = request.Page,
            PageSize = request.PageSize
        };
    }

    private static string SanitizeFts5Query(string input)
    {
        // Escape special FTS5 characters and validate input
        // Prevent injection via column filters, NEAR, etc.
        var sanitized = input
            .Replace("\"", "\"\"")
            .Replace("*", "")
            .Trim();
        return $"\"{sanitized}\"";
    }
}
```

### 5.5 Repository Pattern

Repositories follow the pattern established in the existing JaxSun.Ideas project, with `IRepository<T>` for generic CRUD and specialized repositories for complex queries.

```csharp
public interface IPersonRepository
{
    Task<Person?> GetByIdAsync(int id, CancellationToken ct = default);
    Task<Person?> GetByIdWithRelationshipsAsync(int id, CancellationToken ct = default);
    Task<PagedResult<Person>> GetPagedAsync(PersonFilter filter, CancellationToken ct = default);
    Task<IReadOnlyList<NetworkNode>> GetNetworkAsync(int personId, int depth = 2,
        CancellationToken ct = default);
    Task<IReadOnlyList<Person>> SearchByNameAsync(string query, int limit = 20,
        CancellationToken ct = default);
    Task<Person> CreateAsync(Person person, CancellationToken ct = default);
    Task UpdateAsync(Person person, CancellationToken ct = default);
    Task DeleteAsync(int id, CancellationToken ct = default);
}
```

---

## 6. API Contract Specifications

### 6.1 REST API Endpoints

#### 6.1.1 Documents

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/documents` | List documents (paged, filtered, sorted) |
| `GET` | `/api/documents/{id}` | Get document by ID with full text |
| `GET` | `/api/documents/{id}/entities` | Get extracted entities for document |
| `GET` | `/api/documents/{id}/file` | Stream original PDF file |
| `POST` | `/api/documents` | Create document record |
| `PUT` | `/api/documents/{id}` | Update document metadata |
| `DELETE` | `/api/documents/{id}` | Delete document |

**Query Parameters for `GET /api/documents`:**

```
?page=0
&pageSize=50
&sortBy=document_date
&sortDirection=desc
&documentType=email,court_filing
&dateFrom=2000-01-01
&dateTo=2024-12-31
&extractionStatus=extracted
&isRedacted=false
```

**Response Schema:**

```json
{
  "data": [
    {
      "documentId": 1,
      "eftaNumber": "EFTA00068050",
      "documentTitle": "Email correspondence",
      "documentType": "email",
      "documentDate": "2003-07-15",
      "author": "John Doe",
      "recipient": "Jane Doe",
      "subject": "Meeting arrangements",
      "pageCount": 3,
      "fileSizeBytes": 245760,
      "isRedacted": false,
      "extractionStatus": "extracted",
      "extractionConfidence": 0.92,
      "entityCounts": {
        "people": 5,
        "organizations": 2,
        "locations": 1,
        "events": 1
      },
      "createdAt": "2026-01-15T10:30:00Z"
    }
  ],
  "pagination": {
    "page": 0,
    "pageSize": 50,
    "totalCount": 1234,
    "totalPages": 25
  }
}
```

#### 6.1.2 People

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/people` | List people (paged, filtered) |
| `GET` | `/api/people/{id}` | Get person detail |
| `GET` | `/api/people/{id}/relationships` | Get person's relationships |
| `GET` | `/api/people/{id}/events` | Get events person participated in |
| `GET` | `/api/people/{id}/documents` | Get documents mentioning person |
| `GET` | `/api/people/{id}/financials` | Get financial transactions involving person |
| `GET` | `/api/people/{id}/media` | Get media files featuring person |
| `GET` | `/api/people/{id}/network` | Get N-hop network graph centered on person |
| `POST` | `/api/people` | Create person |
| `PUT` | `/api/people/{id}` | Update person |
| `DELETE` | `/api/people/{id}` | Delete person |
| `POST` | `/api/people/merge` | Merge duplicate person records |

**Network endpoint query parameters:**

```
GET /api/people/{id}/network?depth=2&relationshipTypes=associate,travel_companion
```

#### 6.1.3 Search

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/search` | Full-text search across documents |
| `GET` | `/api/search/entities` | Cross-entity search (people, orgs, locations) |
| `GET` | `/api/search/suggest` | Auto-complete suggestions |

**Search request:**

```
GET /api/search?q=travel+arrangements&page=0&pageSize=20&highlight=true
```

**Search response:**

```json
{
  "query": "travel arrangements",
  "results": [
    {
      "documentId": 42,
      "eftaNumber": "EFTA00068092",
      "documentTitle": "Email: Travel arrangements for July",
      "snippet": "...please confirm the <mark>travel arrangements</mark> for the upcoming...",
      "relevanceScore": 0.95,
      "documentDate": "2004-06-28",
      "documentType": "email"
    }
  ],
  "totalCount": 87,
  "searchTimeMs": 12
}
```

#### 6.1.4 Timeline

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/timeline` | Get timeline events (date-range filtered) |
| `GET` | `/api/timeline/density` | Get event density by time bucket (for heatmap) |

**Timeline request:**

```
GET /api/timeline?dateFrom=2000-01-01&dateTo=2020-12-31&eventTypes=meeting,flight
    &personIds=1,5,12&granularity=month
```

#### 6.1.5 Financial

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/financial/transactions` | List transactions (paged, filtered) |
| `GET` | `/api/financial/flows` | Get Sankey flow data (aggregated by person/org) |
| `GET` | `/api/financial/summary` | Get financial summary statistics |
| `GET` | `/api/financial/patterns` | AI-detected financial patterns |

**Sankey flow response:**

```json
{
  "nodes": [
    { "id": "person_1", "label": "Person A", "type": "person" },
    { "id": "org_3", "label": "Corp XYZ", "type": "organization" }
  ],
  "links": [
    {
      "source": "person_1",
      "target": "org_3",
      "value": 250000.00,
      "transactionCount": 15,
      "dateRange": { "from": "2002-01-01", "to": "2008-12-31" }
    }
  ],
  "totalVolume": 15750000.00,
  "currencyBreakdown": { "USD": 15500000.00, "GBP": 250000.00 }
}
```

#### 6.1.6 Media

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/media` | List media files (paged, filtered by type, date, location) |
| `GET` | `/api/media/{id}` | Get media metadata + analysis |
| `GET` | `/api/media/{id}/file` | Stream media file |
| `GET` | `/api/media/{id}/analysis` | Get AI analysis results |
| `GET` | `/api/media/{id}/entities` | Get visual entities detected in media |
| `POST` | `/api/media/{id}/analyze` | Trigger AI analysis of a media file |

#### 6.1.7 Export

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/export/csv` | Export filtered data as CSV |
| `POST` | `/api/export/json` | Export filtered data as JSON |
| `POST` | `/api/export/pdf-report` | Generate PDF investigation report |
| `POST` | `/api/export/graph` | Export network graph (GEXF, GraphML) |

#### 6.1.8 AI Analysis

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/analysis/extract-entities` | Extract entities from document text |
| `POST` | `/api/analysis/suggest-connections` | AI-suggested connections for a person |
| `POST` | `/api/analysis/detect-patterns` | Detect financial/behavioral patterns |
| `POST` | `/api/analysis/summarize` | Summarize document content |
| `GET` | `/api/analysis/anomalies` | Get detected anomalies across dataset |

### 6.2 GraphQL Endpoint

**Endpoint:** `POST /graphql`

The GraphQL endpoint is designed for the frontend's relationship traversal needs. It supports filtering, sorting, paging, and projections via HotChocolate.

**Schema excerpt:**

```graphql
type Query {
  people(
    where: PersonFilterInput
    order: [PersonSortInput!]
    first: Int
    after: String
  ): PersonConnection

  person(id: Int!): Person

  documents(
    where: DocumentFilterInput
    order: [DocumentSortInput!]
    first: Int
    after: String
  ): DocumentConnection

  relationships(
    where: RelationshipFilterInput
    order: [RelationshipSortInput!]
  ): [Relationship!]!

  networkGraph(
    centerPersonId: Int!
    depth: Int! = 2
    relationshipTypes: [String!]
  ): NetworkGraph!

  connectionPath(
    person1Id: Int!
    person2Id: Int!
    maxDepth: Int! = 4
  ): ConnectionPath
}

type Person {
  personId: Int!
  fullName: String!
  primaryRole: String
  confidenceLevel: String!
  relationshipsFrom: [Relationship!]!
  relationshipsTo: [Relationship!]!
  eventParticipations: [EventParticipant!]!
  mediaAppearances: [MediaPerson!]!
  sentCommunications: [Communication!]!
  financialTransactionsFrom: [FinancialTransaction!]!
  financialTransactionsTo: [FinancialTransaction!]!
}

type NetworkGraph {
  nodes: [NetworkNode!]!
  edges: [NetworkEdge!]!
  centerNodeId: String!
}

type NetworkNode {
  id: String!
  label: String!
  type: NodeType!
  properties: JSON
}

type NetworkEdge {
  source: String!
  target: String!
  relationshipType: String!
  confidenceLevel: String!
  weight: Float!
}

type ConnectionPath {
  found: Boolean!
  path: [Person!]
  relationships: [Relationship!]
  totalHops: Int!
}

enum NodeType {
  PERSON
  ORGANIZATION
  LOCATION
  EVENT
}
```

### 6.3 WebSocket (SignalR Hub)

**Hub Path:** `/hubs/extraction`

```csharp
public interface IExtractionHubClient
{
    // Extraction pipeline progress
    Task ExtractionProgress(ExtractionProgressMessage message);

    // AI analysis progress
    Task AnalysisProgress(AnalysisProgressMessage message);

    // Entity count updates
    Task EntityCountsUpdated(EntityCountsMessage message);

    // Error notifications
    Task ExtractionError(ExtractionErrorMessage message);
}

public class ExtractionProgressMessage
{
    public int DocumentId { get; set; }
    public string EftaNumber { get; set; } = string.Empty;
    public string Stage { get; set; } = string.Empty; // "text_extraction", "ner", "relationship_building"
    public double ProgressPercent { get; set; }
    public int EntitiesFound { get; set; }
    public int RelationshipsFound { get; set; }
    public DateTime Timestamp { get; set; }
}
```

---

## 7. Frontend Component Architecture

### 7.1 Page Layout

The dashboard uses a resizable panel-based layout where the main content area can be split into multiple panes. Each pane hosts one of the core visualization views.

```
+------+------------------------------------------------------------------+
| Side |                     Header / Command Bar                          |
| bar  |------------------------------------------------------------------+
| Nav  |                                                                    |
|      |   +------------------------------+  +---------------------------+  |
| Dash |   |                              |  |                           |  |
| Docs |   |    Primary View Panel        |  |   Detail / Context Panel  |  |
| Ppl  |   |    (Timeline, Network,       |  |   (Entity detail,         |  |
| Net  |   |     Map, Financial,          |  |    Document viewer,       |  |
| Time |   |     Board)                   |  |    AI analysis results)   |  |
| Fin  |   |                              |  |                           |  |
| Media|   |                              |  |                           |  |
| Map  |   |                              |  |                           |  |
| Board|   +------------------------------+  +---------------------------+  |
| Srch |   |            Bottom Panel (Search results, Data table)         |  |
| Set  |   +--------------------------------------------------------------+  |
+------+--------------------------------------------------------------------+
```

### 7.2 Component Hierarchy

```
App
+-- QueryClientProvider (TanStack Query)
+-- SignalRProvider (connection management)
    +-- DashboardLayout
        +-- Sidebar (navigation)
        +-- Header (search bar, notifications, settings)
        +-- PanelGroup (resizable panels via react-resizable-panels)
            +-- [Route-based content]
            |
            +-- DashboardPage
            |   +-- StatsCards (document count, people count, etc.)
            |   +-- RecentActivity feed
            |   +-- MiniTimeline
            |   +-- MiniNetworkGraph
            |
            +-- TimelinePage
            |   +-- TimelineControls (date range, filters, zoom)
            |   +-- EventTimeline (vis-timeline wrapper)
            |   +-- EventDetailPanel
            |
            +-- NetworkPage
            |   +-- NetworkControls (layout, filters, depth)
            |   +-- NetworkGraph (cytoscape.js wrapper)
            |   +-- NodeDetailPanel
            |   +-- PathFinderDialog
            |
            +-- FinancialPage
            |   +-- FinancialFilters
            |   +-- SankeyDiagram (d3-sankey wrapper)
            |   +-- TransactionTable (TanStack Table)
            |   +-- FinancialSummary
            |
            +-- DocumentsPage
            |   +-- DocumentSearch (FTS5 query input)
            |   +-- DocumentList (TanStack Virtual + Table)
            |   +-- DocumentViewer (react-pdf + entity highlights)
            |
            +-- MediaPage
            |   +-- MediaGallery (virtualized grid)
            |   +-- MediaViewer (image/video player)
            |   +-- AIAnalysisOverlay (bounding boxes, labels)
            |
            +-- MapPage
            |   +-- MapControls (layer toggles, clustering)
            |   +-- LocationMap (react-map-gl + MapLibre)
            |   +-- LocationDetailPanel
            |
            +-- InvestigationPage
            |   +-- BoardToolbar (add card, connect, color, export)
            |   +-- InvestigationBoard (@dnd-kit canvas)
            |   +-- BoardCard (entity card with metadata)
            |   +-- BoardConnection (visual links between cards)
            |
            +-- PersonDetailPage
                +-- PersonHeader (name, photo, role, confidence)
                +-- TabGroup
                    +-- RelationshipsTab
                    +-- EventsTab
                    +-- DocumentsTab
                    +-- FinancialsTab
                    +-- MediaTab
                    +-- TimelineTab
```

### 7.3 Visualization Component Patterns

Each visualization library is wrapped in a React component following this pattern:

```tsx
// Example: NetworkGraph.tsx (Cytoscape.js wrapper)

import { useRef, useEffect, useCallback } from 'react';
import cytoscape, { Core, EventObject } from 'cytoscape';
import cola from 'cytoscape-cola';
import { useNetworkData } from '@/hooks/useNetwork';
import { useSelectionStore } from '@/stores/useSelectionStore';
import type { NetworkGraphDto } from '@/types/network';

// Register layout extension once
cytoscape.use(cola);

interface NetworkGraphProps {
  centerPersonId: number;
  depth?: number;
  onNodeSelect?: (nodeId: string, nodeType: string) => void;
}

export function NetworkGraph({
  centerPersonId,
  depth = 2,
  onNodeSelect
}: NetworkGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);

  const { data, isLoading, error } = useNetworkData(centerPersonId, depth);
  const setSelection = useSelectionStore(state => state.setSelection);

  // Initialize Cytoscape instance
  useEffect(() => {
    if (!containerRef.current) return;

    const cy = cytoscape({
      container: containerRef.current,
      style: CYTOSCAPE_STYLES,
      layout: { name: 'cola', animate: true, maxSimulationTime: 3000 },
      minZoom: 0.1,
      maxZoom: 5,
      wheelSensitivity: 0.3,
    });

    cyRef.current = cy;
    return () => { cy.destroy(); };
  }, []);

  // Update data when query results change
  useEffect(() => {
    if (!cyRef.current || !data) return;
    const cy = cyRef.current;

    cy.elements().remove();
    cy.add(transformToElements(data));
    cy.layout({ name: 'cola', animate: true }).run();
  }, [data]);

  // Event handlers
  useEffect(() => {
    if (!cyRef.current) return;
    const cy = cyRef.current;

    const handleTap = (event: EventObject) => {
      const node = event.target;
      if (node.isNode()) {
        setSelection({
          id: node.id(),
          type: node.data('type'),
          label: node.data('label')
        });
        onNodeSelect?.(node.id(), node.data('type'));
      }
    };

    cy.on('tap', 'node', handleTap);
    return () => { cy.off('tap', 'node', handleTap); };
  }, [onNodeSelect, setSelection]);

  if (isLoading) return <LoadingSpinner />;
  if (error) return <ErrorDisplay error={error} />;

  return (
    <div
      ref={containerRef}
      className="w-full h-full min-h-[400px]"
      role="application"
      aria-label="Network relationship graph"
    />
  );
}
```

---

## 8. State Management Approach

### 8.1 State Separation

| State Category | Solution | Rationale |
|---|---|---|
| **Server state** (entities, search results, aggregations) | TanStack React Query | Cache management, background refetch, stale-while-revalidate, request deduplication |
| **Client state** (selections, UI preferences, filter state) | Zustand stores | Simple, synchronous, no context providers needed |
| **Transient state** (form inputs, dialog open/close) | React `useState` | Component-scoped, no sharing needed |
| **Real-time state** (extraction progress, notifications) | Zustand + SignalR listener | SignalR events update Zustand store; components subscribe to store slices |

### 8.2 Zustand Store Definitions

```typescript
// stores/useFilterStore.ts
interface FilterState {
  dateRange: { from: Date | null; to: Date | null };
  selectedPersonIds: number[];
  selectedDocumentTypes: string[];
  selectedRelationshipTypes: string[];
  confidenceThreshold: number; // 0.0 - 1.0
  searchQuery: string;

  // Actions
  setDateRange: (from: Date | null, to: Date | null) => void;
  togglePerson: (personId: number) => void;
  setDocumentTypes: (types: string[]) => void;
  setConfidenceThreshold: (threshold: number) => void;
  setSearchQuery: (query: string) => void;
  resetFilters: () => void;
}

export const useFilterStore = create<FilterState>()(
  persist(
    (set) => ({
      dateRange: { from: null, to: null },
      selectedPersonIds: [],
      selectedDocumentTypes: [],
      selectedRelationshipTypes: [],
      confidenceThreshold: 0.0,
      searchQuery: '',

      setDateRange: (from, to) =>
        set({ dateRange: { from, to } }),
      togglePerson: (personId) =>
        set((state) => ({
          selectedPersonIds: state.selectedPersonIds.includes(personId)
            ? state.selectedPersonIds.filter(id => id !== personId)
            : [...state.selectedPersonIds, personId]
        })),
      setDocumentTypes: (types) =>
        set({ selectedDocumentTypes: types }),
      setConfidenceThreshold: (threshold) =>
        set({ confidenceThreshold: threshold }),
      setSearchQuery: (query) =>
        set({ searchQuery: query }),
      resetFilters: () =>
        set({
          dateRange: { from: null, to: null },
          selectedPersonIds: [],
          selectedDocumentTypes: [],
          selectedRelationshipTypes: [],
          confidenceThreshold: 0.0,
          searchQuery: ''
        }),
    }),
    { name: 'dashboard-filters' }
  )
);
```

```typescript
// stores/useSelectionStore.ts
interface SelectionState {
  selectedEntity: {
    id: string;
    type: 'person' | 'organization' | 'location' | 'event' | 'document';
    label: string;
  } | null;
  hoveredEntity: { id: string; type: string } | null;

  setSelection: (entity: SelectionState['selectedEntity']) => void;
  clearSelection: () => void;
  setHover: (entity: SelectionState['hoveredEntity']) => void;
  clearHover: () => void;
}
```

```typescript
// stores/useBoardStore.ts
interface BoardCard {
  id: string;
  entityId: number;
  entityType: 'person' | 'organization' | 'document' | 'event';
  label: string;
  notes: string;
  color: string;
  position: { x: number; y: number };
  pinned: boolean;
}

interface BoardConnection {
  id: string;
  sourceCardId: string;
  targetCardId: string;
  label: string;
  color: string;
}

interface BoardState {
  cards: BoardCard[];
  connections: BoardConnection[];
  boardName: string;

  addCard: (card: Omit<BoardCard, 'id'>) => void;
  removeCard: (cardId: string) => void;
  updateCardPosition: (cardId: string, position: { x: number; y: number }) => void;
  updateCardNotes: (cardId: string, notes: string) => void;
  addConnection: (conn: Omit<BoardConnection, 'id'>) => void;
  removeConnection: (connId: string) => void;
  clearBoard: () => void;
  exportBoard: () => string; // JSON serialization
  importBoard: (json: string) => void;
}
```

### 8.3 Cross-View Coordination

The filter store acts as a global filter context. When a user selects a person in the network graph, the timeline, financial view, and document list all respond by filtering their data accordingly. This is achieved through shared Zustand selectors rather than prop drilling.

```typescript
// hooks/useFilteredTimeline.ts
export function useFilteredTimeline() {
  const { dateRange, selectedPersonIds, confidenceThreshold } = useFilterStore();

  return useQuery({
    queryKey: ['timeline', dateRange, selectedPersonIds, confidenceThreshold],
    queryFn: () => api.getTimeline({
      dateFrom: dateRange.from?.toISOString(),
      dateTo: dateRange.to?.toISOString(),
      personIds: selectedPersonIds,
      minConfidence: confidenceThreshold,
    }),
    staleTime: 30_000, // 30 seconds before refetch
  });
}
```

---

## 9. AI Integration Architecture

### 9.1 Provider Abstraction

The AI integration mirrors the existing JaxSun.Ideas multi-provider architecture but in a simplified form, since this dashboard is a standalone tool.

```csharp
public interface IAIAnalysisProvider
{
    string ProviderName { get; }
    bool IsAvailable { get; }

    Task<EntityExtractionResult> ExtractEntitiesAsync(
        string documentText,
        CancellationToken ct = default);

    Task<ConnectionSuggestion[]> SuggestConnectionsAsync(
        PersonContext person,
        CancellationToken ct = default);

    Task<FinancialPattern[]> DetectPatternsAsync(
        FinancialDataset dataset,
        CancellationToken ct = default);

    Task<string> SummarizeDocumentAsync(
        string documentText,
        int maxTokens = 500,
        CancellationToken ct = default);

    Task<AnomalyReport> DetectAnomaliesAsync(
        AnalysisContext context,
        CancellationToken ct = default);
}
```

### 9.2 AI Service Layer

```
+---------------------------------------------------+
|              AI Analysis Controller                |
+---------------------------------------------------+
                        |
+---------------------------------------------------+
|           AI Analysis Service (Facade)             |
|  - Routes requests to correct provider             |
|  - Handles fallback (OpenAI -> Claude)             |
|  - Rate limiting, cost tracking                    |
|  - Response caching (identical prompts)            |
+---------------------------------------------------+
            |                        |
+---------------------+   +---------------------+
|   OpenAI Provider   |   |   Claude Provider   |
|   (gpt-4o)          |   |   (claude-sonnet)   |
|                     |   |                     |
|  - Entity extract   |   |  - Entity extract   |
|  - Pattern detect   |   |  - Document summary |
|  - Summarization    |   |  - Connection suggest|
+---------------------+   +---------------------+
```

### 9.3 Entity Extraction Prompt Design

```csharp
public class EntityExtractionService
{
    private const string EXTRACTION_SYSTEM_PROMPT = @"
You are an investigative document analyst. Extract structured entities from
the provided document text. Return ONLY valid JSON matching this schema:

{
  ""people"": [
    {
      ""name"": ""Full Name"",
      ""role"": ""victim|defendant|attorney|judge|witness|investigator|associate|unknown"",
      ""confidence"": 0.0-1.0,
      ""context"": ""brief context of mention""
    }
  ],
  ""organizations"": [
    {
      ""name"": ""Organization Name"",
      ""type"": ""corporation|government|law_firm|financial|nonprofit|unknown"",
      ""confidence"": 0.0-1.0
    }
  ],
  ""locations"": [
    {
      ""name"": ""Location Name"",
      ""type"": ""residence|office|airport|island|hotel|government_building|unknown"",
      ""city"": ""City"",
      ""state"": ""State/Province"",
      ""country"": ""Country"",
      ""confidence"": 0.0-1.0
    }
  ],
  ""dates"": [
    {
      ""date"": ""YYYY-MM-DD"",
      ""context"": ""what happened on this date"",
      ""confidence"": 0.0-1.0
    }
  ],
  ""financialAmounts"": [
    {
      ""amount"": 0.00,
      ""currency"": ""USD"",
      ""context"": ""purpose or description"",
      ""from"": ""payer name or entity"",
      ""to"": ""payee name or entity"",
      ""confidence"": 0.0-1.0
    }
  ],
  ""relationships"": [
    {
      ""person1"": ""Name"",
      ""person2"": ""Name"",
      ""type"": ""employer_employee|associate|legal|financial|familial|unknown"",
      ""description"": ""nature of relationship"",
      ""confidence"": 0.0-1.0
    }
  ]
}

Rules:
- Only extract entities explicitly mentioned in the text
- Do not infer entities not present in the document
- Set confidence below 0.5 for ambiguous mentions
- Use 'unknown' for role/type when uncertain
- Normalize dates to ISO 8601 format
- Financial amounts should be numeric, not formatted strings
";
}
```

### 9.4 Connection Suggestion Engine

The connection suggestion engine operates as a multi-step pipeline:

1. **Context gathering**: Retrieve all known relationships, events, documents, and financial transactions for the target person
2. **Pattern matching**: Use AI to identify patterns similar to known connections (e.g., co-attendance, financial flows, shared addresses)
3. **Confidence scoring**: Rate suggestions on a 0-1 scale based on evidence strength
4. **Deduplication**: Filter out already-known relationships
5. **Human review**: Suggestions are presented for analyst confirmation before persisting

### 9.5 Financial Pattern Detection

```csharp
public class PatternDetectionService
{
    public async Task<FinancialPattern[]> DetectPatternsAsync(
        FinancialDataset dataset, CancellationToken ct)
    {
        // Pre-process: aggregate transactions by month, by pair
        var aggregated = AggregateTransactions(dataset.Transactions);

        // Detect known patterns programmatically (no AI needed)
        var deterministicPatterns = new List<FinancialPattern>();
        deterministicPatterns.AddRange(DetectRoundTripPatterns(aggregated));
        deterministicPatterns.AddRange(DetectStructuringPatterns(aggregated));
        deterministicPatterns.AddRange(DetectRegularPayments(aggregated));

        // Use AI for complex pattern analysis
        var aiPatterns = await _aiProvider.DetectPatternsAsync(
            new PatternContext
            {
                TransactionSummary = aggregated.ToSummary(),
                KnownPatterns = deterministicPatterns,
                TimeRange = dataset.DateRange
            }, ct);

        return deterministicPatterns
            .Concat(aiPatterns)
            .OrderByDescending(p => p.Confidence)
            .ToArray();
    }
}
```

---

## 10. Performance Considerations

### 10.1 Large Dataset Handling

The database may contain 200K+ documents and proportionally large entity counts. The following strategies address this.

| Challenge | Strategy | Implementation |
|---|---|---|
| **Document list (100K+ rows)** | Virtual scrolling | TanStack Virtual with fixed 48px row height; only DOM nodes for visible rows + 20-row overscan |
| **Network graph (1000+ nodes)** | Progressive loading + level of detail | Initial render limited to depth-1 neighbors; expand on click. Nodes beyond viewport use simplified rendering. WebGL renderer option via cytoscape for 5000+ nodes |
| **Timeline (10K+ events)** | Time-bucketed aggregation | Server returns aggregated event counts per time bucket at wide zoom levels; individual events only at narrow zoom |
| **Full-text search** | FTS5 with pre-built index | SQLite FTS5 virtual table with porter stemming tokenizer; sub-50ms queries on 200K documents |
| **Media gallery** | Thumbnail generation + lazy loading | Server-generated thumbnails (200x200); Intersection Observer for lazy loading; virtualized grid |
| **Sankey diagram** | Pre-aggregation | Server aggregates transactions to person-to-person or org-to-org flows; caps at top 50 flows |
| **Map clustering** | Server-side clustering at low zoom | At zoom < 10, server returns clustered location data. At zoom >= 10, individual markers with client-side Supercluster |

### 10.2 Query Optimization

```sql
-- Indexes for common query patterns (added via EF Core migration)

-- People lookup by name (autocomplete)
CREATE INDEX IF NOT EXISTS idx_people_full_name ON people(full_name);

-- Document filtering by date and type
CREATE INDEX IF NOT EXISTS idx_documents_date_type
    ON documents(document_date, document_type);

-- Relationship queries
CREATE INDEX IF NOT EXISTS idx_relationships_person1
    ON relationships(person1_id, relationship_type);
CREATE INDEX IF NOT EXISTS idx_relationships_person2
    ON relationships(person2_id, relationship_type);

-- Event participant lookups
CREATE INDEX IF NOT EXISTS idx_event_participants_person
    ON event_participants(person_id);
CREATE INDEX IF NOT EXISTS idx_event_participants_event
    ON event_participants(event_id);

-- Financial transaction filtering
CREATE INDEX IF NOT EXISTS idx_financial_from_person
    ON financial_transactions(from_person_id, transaction_date);
CREATE INDEX IF NOT EXISTS idx_financial_to_person
    ON financial_transactions(to_person_id, transaction_date);

-- Media file lookups
CREATE INDEX IF NOT EXISTS idx_media_files_type_date
    ON media_files(media_type, date_taken);

-- Extraction status (for pipeline progress)
CREATE INDEX IF NOT EXISTS idx_documents_extraction_status
    ON documents(extraction_status);
```

### 10.3 API Response Optimization

| Technique | Details |
|---|---|
| **Cursor-based pagination** | GraphQL uses cursor-based pagination (Relay-style `first`/`after`) for consistent results during concurrent writes |
| **Server-side projection** | HotChocolate's `[UseProjection]` attribute generates `SELECT` queries that fetch only requested fields |
| **ETag / If-None-Match** | REST endpoints return ETag headers; clients skip processing when data has not changed |
| **Response compression** | Brotli compression at Nginx layer (typical 70-90% reduction for JSON payloads) |
| **Query deduplication** | TanStack Query deduplicates identical in-flight requests automatically |
| **Stale-while-revalidate** | TanStack Query serves cached data immediately while refetching in background |

### 10.4 SQLite Concurrency Considerations

SQLite uses file-level locking. The dashboard is primarily read-heavy with occasional writes (entity edits, AI analysis results). The following settings optimize for this access pattern.

```csharp
// In EpsteinDbContext configuration
optionsBuilder.UseSqlite(connectionString, options =>
{
    // WAL mode allows concurrent reads during writes
    // Set via PRAGMA at connection open
});

// Connection string includes WAL mode
// "Data Source=epstein_documents.db;Mode=ReadWriteCreate;Cache=Shared"

// Startup: ensure WAL mode is enabled
public class DatabaseStartupService : IHostedService
{
    public async Task StartAsync(CancellationToken ct)
    {
        using var connection = new SqliteConnection(connectionString);
        await connection.OpenAsync(ct);
        using var command = connection.CreateCommand();
        command.CommandText = "PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000;";
        await command.ExecuteNonQueryAsync(ct);
    }
}
```

---

## 11. Security Architecture

### 11.1 Threat Model

Since this is a self-hosted investigative tool, the primary threats differ from a public-facing application.

| Threat | Severity | Mitigation |
|---|---|---|
| **Unauthorized network access** | High | Nginx TLS termination; firewall rules; no public exposure |
| **SQL injection via search** | High | FTS5 query sanitization; parameterized queries everywhere; Dapper uses parameters |
| **Path traversal (file serving)** | High | Whitelist document file directory; validate file paths against known document records |
| **AI prompt injection** | Medium | Document text is pre-sanitized before AI prompts; system prompts use clear delimiters |
| **CORS misconfiguration** | Medium | Strict CORS policy (only dashboard origin allowed) |
| **Sensitive data exposure** | Medium | No PII in logs; structured logging with redaction |
| **Denial of service** | Low | Rate limiting on AI endpoints; query timeout on database |

### 11.2 Security Implementations

```csharp
// Program.cs security configuration

// CORS - restrict to dashboard origin only
builder.Services.AddCors(options =>
{
    options.AddPolicy("DashboardOnly", policy =>
    {
        policy.WithOrigins(
                builder.Configuration["AllowedOrigins"] ?? "https://localhost:3000")
            .AllowAnyHeader()
            .AllowAnyMethod()
            .AllowCredentials(); // Required for SignalR
    });
});

// Rate limiting on AI endpoints
builder.Services.AddRateLimiter(options =>
{
    options.AddFixedWindowLimiter("ai-analysis", opt =>
    {
        opt.PermitLimit = 10;
        opt.Window = TimeSpan.FromMinutes(1);
        opt.QueueProcessingOrder = QueueProcessingOrder.OldestFirst;
        opt.QueueLimit = 5;
    });
});

// File path validation
public class FileSecurityService
{
    private readonly string _allowedBasePath;

    public bool IsPathAllowed(string requestedPath)
    {
        var fullPath = Path.GetFullPath(requestedPath);
        return fullPath.StartsWith(_allowedBasePath, StringComparison.OrdinalIgnoreCase);
    }
}

// Input sanitization middleware
app.Use(async (context, next) =>
{
    // Log request (without sensitive data)
    Log.Information("Request: {Method} {Path}",
        context.Request.Method, context.Request.Path);
    await next();
});
```

### 11.3 API Key Management

AI provider API keys are stored in environment variables, never in source code or configuration files committed to version control.

```yaml
# docker-compose.yml - API keys via environment variables
services:
  api:
    environment:
      - AI__OpenAI__ApiKey=${OPENAI_API_KEY}
      - AI__Claude__ApiKey=${CLAUDE_API_KEY}
```

---

## 12. Docker Deployment Configuration

### 12.1 Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  # Nginx reverse proxy
  nginx:
    image: nginx:1.27-alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
      - frontend-build:/usr/share/nginx/html:ro
    depends_on:
      api:
        condition: service_healthy
    restart: unless-stopped
    networks:
      - dashboard-net

  # ASP.NET Core API
  api:
    build:
      context: ./backend
      dockerfile: src/EpsteinDashboard.Api/Dockerfile
    environment:
      - ASPNETCORE_ENVIRONMENT=Production
      - ASPNETCORE_URLS=http://+:5000
      - ConnectionStrings__EpsteinDb=Data Source=/data/epstein_documents.db;Mode=ReadWriteCreate;Cache=Shared
      - AI__OpenAI__ApiKey=${OPENAI_API_KEY:-}
      - AI__OpenAI__Model=${OPENAI_MODEL:-gpt-4o}
      - AI__Claude__ApiKey=${CLAUDE_API_KEY:-}
      - AI__Claude__Model=${CLAUDE_MODEL:-claude-sonnet-4-20250514}
      - AllowedOrigins=https://localhost,http://localhost
      - DocumentFilesPath=/data/epstein_files
    volumes:
      - ${DATA_PATH:-../extraction_output}:/data:rw
      - ${FILES_PATH:-../epstein_files}:/data/epstein_files:ro
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 15s
    restart: unless-stopped
    networks:
      - dashboard-net

  # Frontend build (multi-stage: build then serve via nginx)
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    volumes:
      - frontend-build:/app/dist

volumes:
  frontend-build:

networks:
  dashboard-net:
    driver: bridge
```

### 12.2 Backend Dockerfile

```dockerfile
# backend/src/EpsteinDashboard.Api/Dockerfile
FROM mcr.microsoft.com/dotnet/sdk:9.0 AS build
WORKDIR /src

# Copy solution and project files
COPY EpsteinDashboard.sln .
COPY src/EpsteinDashboard.Core/*.csproj src/EpsteinDashboard.Core/
COPY src/EpsteinDashboard.Application/*.csproj src/EpsteinDashboard.Application/
COPY src/EpsteinDashboard.Infrastructure/*.csproj src/EpsteinDashboard.Infrastructure/
COPY src/EpsteinDashboard.Api/*.csproj src/EpsteinDashboard.Api/
RUN dotnet restore

# Copy source and build
COPY src/ src/
RUN dotnet publish src/EpsteinDashboard.Api/EpsteinDashboard.Api.csproj \
    -c Release -o /app/publish --no-restore

# Runtime image
FROM mcr.microsoft.com/dotnet/aspnet:9.0 AS runtime
WORKDIR /app
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
COPY --from=build /app/publish .

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser
USER appuser

EXPOSE 5000
ENTRYPOINT ["dotnet", "EpsteinDashboard.Api.dll"]
```

### 12.3 Frontend Dockerfile

```dockerfile
# frontend/Dockerfile
FROM node:22-alpine AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

# Output stage - copy build artifacts to shared volume
FROM alpine:3.20
COPY --from=build /app/dist /app/dist
```

### 12.4 Nginx Configuration

```nginx
# nginx/nginx.conf
worker_processes auto;

events {
    worker_connections 1024;
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;
    sendfile      on;
    keepalive_timeout 65;

    # Compression
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css text/xml text/javascript
               application/json application/javascript application/xml
               application/rss+xml image/svg+xml;

    # Brotli (if module available)
    # brotli on;
    # brotli_comp_level 6;
    # brotli_types text/plain text/css text/xml text/javascript
    #              application/json application/javascript;

    upstream api_backend {
        server api:5000;
    }

    server {
        listen 80;
        server_name _;

        # API proxy
        location /api/ {
            proxy_pass http://api_backend;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_read_timeout 300s;

            # Increase buffer for large responses
            proxy_buffer_size 128k;
            proxy_buffers 4 256k;
            proxy_busy_buffers_size 256k;
        }

        # GraphQL endpoint
        location /graphql {
            proxy_pass http://api_backend;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }

        # SignalR WebSocket
        location /hubs/ {
            proxy_pass http://api_backend;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_cache_bypass $http_upgrade;
            proxy_read_timeout 3600s;
        }

        # Health check
        location /health {
            proxy_pass http://api_backend;
        }

        # Static frontend files
        location / {
            root /usr/share/nginx/html;
            index index.html;
            try_files $uri $uri/ /index.html;

            # Cache static assets aggressively
            location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff2?)$ {
                expires 1y;
                add_header Cache-Control "public, immutable";
            }
        }
    }
}
```

---

## 13. Development Environment Setup

### 13.1 Prerequisites

| Tool | Version | Notes |
|---|---|---|
| .NET SDK | 9.0.x | `dotnet --version` |
| Node.js | 22.x LTS | `node --version` |
| npm | 10.x+ | Bundled with Node.js |
| Docker Desktop | 27.x | For containerized deployment |
| Git | 2.40+ | Source control |
| IDE (backend) | Visual Studio 2022 / VS Code + C# Dev Kit | Debugging, IntelliSense |
| IDE (frontend) | VS Code + ESLint + Tailwind CSS IntelliSense | TypeScript development |

### 13.2 Quick Start

```bash
# Clone and navigate
cd C:\Development\JaxSun.Ideas\tools\EpsteinDownloader\dashboard

# Backend setup
cd backend
dotnet restore
dotnet build

# Verify database exists
ls ../extraction_output/epstein_documents.db

# Run backend (development mode)
dotnet run --project src/EpsteinDashboard.Api

# Frontend setup (separate terminal)
cd frontend
npm install
npm run dev

# Full stack via Docker
docker compose up --build
```

### 13.3 Development Configuration

```json
// backend/src/EpsteinDashboard.Api/appsettings.Development.json
{
  "ConnectionStrings": {
    "EpsteinDb": "Data Source=../../../../extraction_output/epstein_documents.db;Mode=ReadWriteCreate;Cache=Shared"
  },
  "DocumentFilesPath": "../../../../epstein_files",
  "AllowedOrigins": "http://localhost:5173",
  "AI": {
    "OpenAI": {
      "ApiKey": "",
      "Model": "gpt-4o",
      "MaxTokens": 4096,
      "Temperature": 0.1,
      "Enabled": true
    },
    "Claude": {
      "ApiKey": "",
      "Model": "claude-sonnet-4-20250514",
      "MaxTokens": 4096,
      "Temperature": 0.1,
      "Enabled": true
    }
  },
  "Logging": {
    "LogLevel": {
      "Default": "Information",
      "Microsoft.EntityFrameworkCore": "Warning"
    }
  }
}
```

```typescript
// frontend/vite.config.ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react-swc';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      '/graphql': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      '/hubs': {
        target: 'http://localhost:5000',
        ws: true,
        changeOrigin: true,
      },
    },
  },
});
```

---

## 14. Build and Deployment Pipeline

### 14.1 GitHub Actions CI/CD

```yaml
# .github/workflows/dashboard-ci.yml
name: Dashboard CI/CD

on:
  push:
    branches: [main, primary]
    paths:
      - 'tools/EpsteinDownloader/dashboard/**'
  pull_request:
    branches: [main]
    paths:
      - 'tools/EpsteinDownloader/dashboard/**'

jobs:
  backend-build-test:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: tools/EpsteinDownloader/dashboard/backend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-dotnet@v4
        with:
          dotnet-version: '9.0.x'
      - run: dotnet restore
      - run: dotnet build --no-restore
      - run: dotnet test --no-build --verbosity normal
        --collect:"XPlat Code Coverage"

  frontend-build-test:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: tools/EpsteinDownloader/dashboard/frontend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '22'
          cache: 'npm'
          cache-dependency-path: tools/EpsteinDownloader/dashboard/frontend/package-lock.json
      - run: npm ci
      - run: npm run lint
      - run: npm run type-check
      - run: npm run build

  docker-build:
    needs: [backend-build-test, frontend-build-test]
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - run: docker compose -f tools/EpsteinDownloader/dashboard/docker-compose.yml build
```

### 14.2 Local Build Commands

```bash
# Backend
dotnet build                           # Compile
dotnet test                            # Run tests
dotnet run --project src/EpsteinDashboard.Api  # Run dev server

# Frontend
npm run dev                            # Dev server with HMR (port 5173)
npm run build                          # Production build
npm run preview                        # Preview production build
npm run lint                           # ESLint
npm run type-check                     # TypeScript type checking (tsc --noEmit)

# Docker (full stack)
docker compose up --build              # Build and start all services
docker compose up -d                   # Start in background
docker compose down                    # Stop all services
docker compose logs -f api             # Follow API logs
```

---

## 15. AI API Cost Estimates

### 15.1 Per-Operation Costs (Estimated)

| Operation | Model | Input Tokens | Output Tokens | Cost per Call |
|---|---|---|---|---|
| Entity Extraction (1 document) | gpt-4o | ~4,000 | ~1,500 | ~$0.025 |
| Connection Suggestion (1 person) | gpt-4o | ~3,000 | ~1,000 | ~$0.018 |
| Document Summarization | gpt-4o-mini | ~4,000 | ~500 | ~$0.001 |
| Pattern Detection (batch) | gpt-4o | ~8,000 | ~2,000 | ~$0.045 |
| Anomaly Detection (dataset) | claude-sonnet | ~10,000 | ~3,000 | ~$0.054 |
| Image Analysis (1 image) | gpt-4o (vision) | ~1,000 + image | ~500 | ~$0.015 |

### 15.2 Projected Monthly Costs by Usage Tier

| Usage Tier | Documents/Month | Analysis Calls/Month | Estimated Monthly Cost |
|---|---|---|---|
| **Light** (occasional investigation) | 100 docs extracted | 50 analysis calls | ~$5-10 |
| **Medium** (active investigation) | 1,000 docs extracted | 500 analysis calls | ~$40-80 |
| **Heavy** (full dataset processing) | 10,000 docs extracted | 2,000 analysis calls | ~$300-500 |
| **Bulk extraction** (initial pipeline run) | 200,000 docs (one-time) | 200K extractions | ~$5,000 (one-time) |

### 15.3 Cost Mitigation Strategies

1. **Response caching**: Cache AI responses for identical document text (hash-based key). Extraction of the same document should never call the API twice.
2. **Tiered models**: Use `gpt-4o-mini` for simple tasks (summarization, classification) and `gpt-4o` only for complex analysis (entity extraction, pattern detection).
3. **Batch processing**: Group multiple short documents into a single API call where token budget allows.
4. **Local NER first**: The existing spaCy NER pipeline handles basic entity extraction without AI API costs. AI is used only for disambiguation, relationship inference, and complex analysis.
5. **User-initiated only**: AI analysis calls are triggered by explicit user action, never automatically on page load.

---

## 16. Risk Assessment and Mitigations

### 16.1 Technical Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| **SQLite write contention** when extraction pipeline runs concurrently with dashboard writes | Medium | Medium | WAL mode, busy_timeout=5000ms, retry logic in repositories, extraction pipeline uses separate connection |
| **Cytoscape.js performance degradation** with 5000+ nodes | Medium | High | Limit initial render to 2-hop neighborhood; use WebGL renderer for large graphs; implement level-of-detail rendering |
| **FTS5 index grows large** with 200K+ documents | Low | Medium | FTS5 content-less tables option if storage is a concern; monitor index size; optimize tokenizer settings |
| **AI API rate limits** during bulk extraction | High | Medium | Exponential backoff with jitter; queue system with configurable concurrency; fallback between providers |
| **Docker volume permissions** for SQLite database file | Medium | High | Explicit UID/GID mapping in Dockerfile; documentation for host filesystem permissions |
| **MapLibre tile server dependency** for offline use | Medium | Low | Bundle basic OSM tiles for offline mode; configure tile server URL in settings |
| **React state consistency** across multiple visualization panels | Medium | Medium | Zustand stores as single source of truth; TanStack Query cache invalidation on mutations |
| **PDF rendering performance** for large documents (100+ pages) | Low | Medium | Page-level lazy loading via react-pdf; server-side page image generation as fallback |

### 16.2 Operational Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| **AI API key exposure** in environment variables or logs | Low | Critical | Environment variables only (never in config files); log redaction; Docker secrets for production |
| **Data loss** during schema migration | Low | Critical | Database backup before any migration; migration tested against copy first |
| **Stale FTS5 index** if triggers are not created | Medium | Medium | Application startup verifies trigger existence; health check includes FTS index validation |
| **Container disk space** exhaustion from logs | Medium | Low | Log rotation in Serilog config; Docker log driver limits; periodic cleanup |

### 16.3 Development Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| **d3-sankey library unmaintained** (last release 6 years ago) | Medium | Low | Library is stable and feature-complete; alternatives (plotly, nivo) available if needed; minimal API surface reduces breakage risk |
| **vis-timeline React integration complexity** | Medium | Medium | Use imperative ref-based wrapper pattern (not declarative); community wrappers available as reference |
| **EF Core SQLite column mapping mismatches** | High | Medium | Integration tests validate model-to-schema alignment at startup; snake_case to PascalCase mapping tested |
| **HotChocolate version upgrade breaks GraphQL schema** | Low | Medium | Pin to 15.1.x; schema snapshot tests; breaking changes tracked in upgrade guide |

---

## Appendix A: Database Schema Reference

### Tables and Column Counts

| Table | Columns | Primary Key | Key Foreign Keys |
|---|---|---|---|
| `documents` | 18 | `document_id` | -- |
| `people` | 16 | `person_id` | `first_mentioned_in_doc_id` -> documents |
| `organizations` | 8 | `organization_id` | `parent_organization_id` -> self, `first_mentioned_in_doc_id` -> documents |
| `locations` | 13 | `location_id` | `owner_person_id` -> people, `owner_organization_id` -> organizations |
| `events` | 14 | `event_id` | `location_id` -> locations, `source_document_id` -> documents |
| `relationships` | 10 | `relationship_id` | `person1_id` -> people, `person2_id` -> people |
| `event_participants` | 6 | `participant_id` | `event_id` -> events, `person_id` -> people, `organization_id` -> organizations |
| `communications` | 11 | `communication_id` | `sender_person_id` -> people, `source_document_id` -> documents |
| `communication_recipients` | 5 | `recipient_id` | `communication_id` -> communications, `person_id` -> people |
| `financial_transactions` | 15 | `transaction_id` | `from_person_id`/`to_person_id` -> people, `from_organization_id`/`to_organization_id` -> organizations |
| `evidence_items` | 11 | `evidence_id` | `seized_from_location_id` -> locations, `source_document_id` -> documents |
| `media_files` | 22 | `media_file_id` | `source_document_id` -> documents, `location_id` -> locations |
| `image_analysis` | 18 | `analysis_id` | `media_file_id` -> media_files |
| `visual_entities` | 14 | `entity_id` | `media_file_id` -> media_files, `person_id` -> people |
| `media_people` | 12 | `media_person_id` | `media_file_id` -> media_files, `person_id` -> people |
| `media_events` | 6 | `media_event_id` | `media_file_id` -> media_files, `event_id` -> events |
| `extraction_log` | 10 | `log_id` | `document_id` -> documents, `media_file_id` -> media_files |

### Entity Relationship Diagram (Key Relationships)

```
                    +-------------+
                    |  documents  |
                    +------+------+
                           |
          +----------------+----------------+
          |                |                |
    +-----+------+   +----+-----+    +-----+-------+
    |   people   |   |  events  |    | media_files |
    +-----+------+   +----+-----+    +------+------+
          |                |                |
    +-----+------+   +----+--------+  +----+----------+
    |relationships|  |event_       |  |image_analysis |
    +------------+   |participants |  +---------------+
          |          +--------------+  |visual_entities|
    +-----+-------+                    +---------------+
    |communications|                   |media_people   |
    +-----+-------+                    +---------------+
          |                            |media_events   |
    +-----+-----------+                +---------------+
    |communication_   |
    |recipients       |
    +-----------------+

    +---------------------+     +----------------+
    |financial_transactions|    | evidence_items |
    +---------------------+     +----------------+

    +-----------------+     +----------------+
    | organizations   |     |   locations    |
    +-----------------+     +----------------+

    +-----------------+
    | extraction_log  |
    +-----------------+
```

---

## Appendix B: API Response Schemas

### B.1 Standard Envelope

All REST API responses use a consistent envelope.

```json
{
  "data": {},
  "pagination": {
    "page": 0,
    "pageSize": 50,
    "totalCount": 1234,
    "totalPages": 25
  },
  "meta": {
    "requestId": "uuid",
    "timestamp": "2026-02-03T12:00:00Z",
    "duration": 45
  }
}
```

### B.2 Error Response

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "One or more validation errors occurred.",
    "details": [
      {
        "field": "pageSize",
        "message": "Page size must be between 1 and 200."
      }
    ]
  },
  "meta": {
    "requestId": "uuid",
    "timestamp": "2026-02-03T12:00:00Z"
  }
}
```

### B.3 Network Graph Response

```json
{
  "data": {
    "centerNodeId": "person_42",
    "nodes": [
      {
        "id": "person_42",
        "label": "Person Name",
        "type": "person",
        "properties": {
          "primaryRole": "associate",
          "confidenceLevel": "high",
          "connectionCount": 15
        }
      },
      {
        "id": "org_7",
        "label": "Organization Name",
        "type": "organization",
        "properties": {
          "organizationType": "corporation"
        }
      }
    ],
    "edges": [
      {
        "source": "person_42",
        "target": "person_18",
        "relationshipType": "professional_associate",
        "confidenceLevel": "high",
        "weight": 3.0,
        "properties": {
          "startDate": "2002-01-01",
          "sourceDocumentCount": 5
        }
      }
    ],
    "stats": {
      "totalNodes": 34,
      "totalEdges": 67,
      "maxDepth": 2
    }
  }
}
```

### B.4 Timeline Response

```json
{
  "data": {
    "events": [
      {
        "eventId": 123,
        "type": "meeting",
        "title": "Meeting at Location X",
        "start": "2003-07-15T14:00:00Z",
        "end": "2003-07-15T16:00:00Z",
        "group": "person_42",
        "content": "Meeting between Person A and Person B",
        "confidenceLevel": "high",
        "participantCount": 3,
        "sourceDocumentId": 456,
        "className": "event-meeting"
      }
    ],
    "groups": [
      {
        "id": "person_42",
        "content": "Person Name",
        "order": 1
      }
    ],
    "dateRange": {
      "min": "2000-01-01",
      "max": "2020-12-31"
    }
  }
}
```

---

*End of Technical PRD*
