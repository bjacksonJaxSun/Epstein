# Investigative Document Analysis Dashboard - Product Requirements Document

**Version:** 1.0
**Date:** 2026-02-03
**Author:** Software Designer
**Status:** Draft for Review

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [User Personas and Use Cases](#2-user-personas-and-use-cases)
3. [Information Architecture and Navigation](#3-information-architecture-and-navigation)
4. [Visual Design System](#4-visual-design-system)
5. [Page and View Specifications](#5-page-and-view-specifications)
6. [Component Inventory](#6-component-inventory)
7. [Interaction Patterns](#7-interaction-patterns)
8. [Data Visualization Specifications](#8-data-visualization-specifications)
9. [AI Feature Workflows](#9-ai-feature-workflows)
10. [Investigative Workflow Features](#10-investigative-workflow-features)
11. [Responsive Design Considerations](#11-responsive-design-considerations)
12. [Accessibility Requirements](#12-accessibility-requirements)
13. [Performance Requirements](#13-performance-requirements)
14. [Recommended Technology Stack](#14-recommended-technology-stack)

---

## 1. Executive Summary

### 1.1 Product Vision

The Investigative Document Analysis Dashboard is a self-hosted, single-page web application designed for researchers, journalists, and analysts working with large document collections. It transforms a structured SQLite database of extracted entities -- people, organizations, events, locations, financial transactions, communications, and media files -- into an interactive analytical workspace.

The application enables users to explore connections between entities, trace financial flows, visualize events on timelines and maps, search full-text document content, and leverage AI-assisted analysis to surface patterns and anomalies that would be invisible in raw data.

### 1.2 Goals and Success Metrics

| Goal | Success Metric |
|------|----------------|
| Enable rapid entity discovery | Users can locate any person, organization, or event within 3 interactions |
| Surface hidden connections | Relationship paths between any two people displayed in under 2 seconds |
| Support deep-dive analysis | Users can cross-reference across all data types from any entity detail view |
| Maintain analytical context | Investigation boards preserve user hypotheses and pinned findings across sessions |
| Ensure data integrity trust | Confidence scores and source documents displayed on every derived insight |

### 1.3 Scope

This PRD covers the user experience design for a read-only analytical dashboard. The underlying database is populated by a separate extraction pipeline. This application does not modify the source data; it adds an analytical layer (bookmarks, annotations, investigation boards) stored in a separate local storage mechanism or companion database table.

---

## 2. User Personas and Use Cases

### 2.1 Primary Personas

#### Persona A: The Investigative Journalist

- **Name:** Maria Chen
- **Role:** Senior investigative reporter at a mid-size publication
- **Technical Skill:** Moderate. Comfortable with spreadsheets and basic database queries. Not a developer.
- **Goals:** Find connections between individuals and financial flows that constitute a publishable story. Needs to trace who met whom, when, where, and whether money changed hands.
- **Pain Points:** Overwhelmed by volume. Thousands of documents, hundreds of names. Cannot hold all connections in her head. Needs visual tools to see the network.
- **Key Workflows:**
  - Search for a person by name, then explore all their connections
  - View a timeline of events involving a specific group of people
  - Trace financial transactions between two parties
  - Export findings with source citations for editorial review

#### Persona B: The Academic Researcher

- **Name:** Dr. James Okafor
- **Role:** Political science professor studying institutional corruption patterns
- **Technical Skill:** High. Experienced with data analysis tools, R, Python. Values methodological rigor.
- **Goals:** Identify systemic patterns across time periods and organizational structures. Interested in network centrality, financial flow patterns, and temporal clustering of events.
- **Pain Points:** Needs to verify every claim against source documents. Cannot rely on AI-derived connections without seeing the underlying evidence. Wants to export structured data for further statistical analysis.
- **Key Workflows:**
  - Network analysis of relationship graphs with filtering by type and confidence level
  - Statistical overview of financial transaction patterns
  - Bulk export of filtered datasets
  - Cross-referencing event clusters with communication patterns

#### Persona C: The Citizen Analyst

- **Name:** Sarah Kim
- **Role:** Independent researcher and open-source intelligence enthusiast
- **Technical Skill:** Low to moderate. Web-literate but not technical. Relies on the application to do the heavy lifting.
- **Goals:** Understand the big picture. Who are the key players? What are the major events? Where did things happen?
- **Pain Points:** Does not know where to start. Needs guided entry points and suggested starting places. Can get lost in complexity.
- **Key Workflows:**
  - Start from the overview dashboard with key statistics
  - Browse the most-connected people list
  - Explore the map to understand geographic scope
  - Follow suggested connections from AI analysis

### 2.2 Core Use Cases

| ID | Use Case | Persona | Priority |
|----|----------|---------|----------|
| UC-01 | Search for a person and view their complete profile with all connections | All | Critical |
| UC-02 | Explore the relationship network graph centered on a selected individual | A, B | Critical |
| UC-03 | View events on an interactive timeline with filtering by type, person, and date range | All | Critical |
| UC-04 | Trace financial flows between parties using Sankey diagrams | A, B | Critical |
| UC-05 | Full-text search across all documents with highlighted results | All | Critical |
| UC-06 | View locations on an interactive map with event and media overlays | All | High |
| UC-07 | Browse media gallery with AI analysis results and person identification | A, C | High |
| UC-08 | Create investigation boards to organize and annotate findings | A, B | High |
| UC-09 | Pin and bookmark entities of interest for quick access | All | High |
| UC-10 | AI-assisted pattern detection and anomaly surfacing | A, B | High |
| UC-11 | Export investigation findings as structured reports | A, B | Medium |
| UC-12 | Cross-reference entities across all data types from any detail view | All | Critical |
| UC-13 | Filter and sort all entity lists by confidence level, date, and source | B | High |
| UC-14 | View document viewer with original text and extracted entity highlighting | All | High |
| UC-15 | Compare communication patterns between individuals over time | A, B | Medium |

---

## 3. Information Architecture and Navigation

### 3.1 Application Shell

The application uses a persistent shell layout with three zones:

```
+---------------------------------------------------------------+
|  [Logo] INVESTIGATIVE DASHBOARD          [Search] [Pins] [?]  |  <- Top Bar (56px)
+----------+----------------------------------------------------+
|          |                                                    |
|  PRIMARY |              MAIN CONTENT AREA                     |
|   NAV    |                                                    |
|          |  (Switches between views based on nav selection)   |
|  (64px)  |                                                    |
|          |                                                    |
|          +----------------------------------------------------+
|          |           DETAIL / CONTEXT PANEL                   |
|          |     (Slides in from right, 400px wide)             |
+----------+----------------------------------------------------+
```

### 3.2 Primary Navigation (Left Sidebar - Icon Rail)

The left sidebar is a narrow icon rail (64px wide) that expands to 240px on hover or click. Navigation items are organized by analytical function:

| Position | Icon | Label | Route | Description |
|----------|------|-------|-------|-------------|
| 1 | Grid/Dashboard | Overview | `/` | Key statistics and entry points |
| 2 | Users | People | `/people` | Person directory and search |
| 3 | Building | Organizations | `/organizations` | Organization directory |
| 4 | GitBranch | Network | `/network` | Relationship network graph |
| 5 | Calendar | Timeline | `/timeline` | Event timeline |
| 6 | DollarSign | Financial | `/financial` | Financial flow analysis |
| 7 | FileText | Documents | `/documents` | Document viewer and search |
| 8 | Image | Media | `/media` | Media gallery |
| 9 | MapPin | Map | `/map` | Geographic visualization |
| 10 | MessageSquare | Communications | `/communications` | Email and letter analysis |
| 11 | Clipboard | Evidence | `/evidence` | Physical evidence tracking |
| --- | --- | --- | --- | --- |
| 12 | Layout | Boards | `/boards` | Investigation boards |
| 13 | Bookmark | Bookmarks | `/bookmarks` | Pinned items |
| 14 | Sparkles | AI Insights | `/ai-insights` | AI-generated analysis |
| 15 | Settings | Settings | `/settings` | Configuration |

### 3.3 Global Search

A persistent search bar in the top bar provides universal search across all entity types. The search interface supports:

- **Instant results** as the user types (debounced at 200ms)
- **Categorized results** grouped by entity type (People, Organizations, Documents, Events, Locations, Communications)
- **Result count badges** showing how many matches per category
- **Keyboard navigation** through results (arrow keys, Enter to select, Escape to close)
- **Search operators** for advanced users: `type:person`, `date:2005-2010`, `confidence:high`
- **Recent searches** displayed when the search field is focused with no input

### 3.4 Context Panel (Right Slide-Out)

Clicking any entity anywhere in the application opens a context panel from the right edge. This panel provides a quick summary without navigating away from the current view. The panel includes:

- Entity summary header with name, type badge, and confidence indicator
- Tabbed content: Overview, Connections, Documents, Timeline, Notes
- Action buttons: Pin, Add to Board, View Full Detail, Copy Link
- Close button and click-outside-to-dismiss behavior

### 3.5 Breadcrumb and Navigation State

The application maintains breadcrumb state for deep navigation paths. Example:

```
Overview > People > Jeffrey Epstein > Relationships > Ghislaine Maxwell
```

The browser URL updates with each navigation, enabling back/forward button usage and deep linking.

---

## 4. Visual Design System

### 4.1 Design Philosophy

The visual language is modeled on professional intelligence analysis workstations. The design prioritizes information density, visual clarity, and sustained readability over decorative elements. Every pixel serves an analytical purpose.

Core principles:
- **Dark theme as default** to reduce eye strain during extended analysis sessions
- **Information hierarchy through luminance** rather than color alone
- **Restrained use of color** reserved for data encoding, status indicators, and interactive affordances
- **Typographic clarity** with a monospace option for document content and identifiers

### 4.2 Color Palette

#### Surface Colors (Background Hierarchy)

| Token | Value | Usage |
|-------|-------|-------|
| `--surface-ground` | `#0A0A0F` | Application background, deepest layer |
| `--surface-base` | `#12121A` | Primary content area background |
| `--surface-raised` | `#1A1A25` | Cards, panels, raised surfaces |
| `--surface-overlay` | `#222230` | Modals, dropdown menus, tooltips |
| `--surface-elevated` | `#2A2A3A` | Hovered cards, active states |

#### Text Colors

| Token | Value | Contrast on `--surface-base` | Usage |
|-------|-------|------------------------------|-------|
| `--text-primary` | `#E8E8ED` | 13.2:1 | Primary text, headings |
| `--text-secondary` | `#A0A0B0` | 7.1:1 | Secondary labels, descriptions |
| `--text-tertiary` | `#6B6B7B` | 4.5:1 | Tertiary info, timestamps |
| `--text-disabled` | `#454555` | 3.1:1 | Disabled states (large text only) |

#### Accent Colors (Data Encoding)

| Token | Value | Semantic Meaning |
|-------|-------|------------------|
| `--accent-blue` | `#4A9EFF` | People, primary actions |
| `--accent-emerald` | `#34D399` | Organizations, success states |
| `--accent-amber` | `#FBBF24` | Events, warnings |
| `--accent-red` | `#F87171` | Financial, errors, high-risk |
| `--accent-purple` | `#A78BFA` | Communications |
| `--accent-cyan` | `#22D3EE` | Locations, maps |
| `--accent-orange` | `#FB923C` | Media files |
| `--accent-rose` | `#FB7185` | Evidence items |

#### Confidence Level Colors

| Level | Color | Usage |
|-------|-------|-------|
| High | `#34D399` (emerald) | Verified or high-confidence data |
| Medium | `#FBBF24` (amber) | Moderate confidence, needs verification |
| Low | `#F87171` (red) | Low confidence, use with caution |
| Unverified | `#6B6B7B` (gray) | Not yet assessed |

### 4.3 Typography

| Role | Font | Weight | Size | Line Height |
|------|------|--------|------|-------------|
| Display (page titles) | Inter | 600 | 24px | 32px |
| Heading 1 | Inter | 600 | 20px | 28px |
| Heading 2 | Inter | 500 | 16px | 24px |
| Body | Inter | 400 | 14px | 20px |
| Body Small | Inter | 400 | 12px | 16px |
| Caption | Inter | 400 | 11px | 14px |
| Code / EFTA numbers | JetBrains Mono | 400 | 13px | 18px |
| Document content | JetBrains Mono | 400 | 14px | 22px |

### 4.4 Spacing Scale

Based on a 4px grid:

| Token | Value |
|-------|-------|
| `--space-1` | 4px |
| `--space-2` | 8px |
| `--space-3` | 12px |
| `--space-4` | 16px |
| `--space-5` | 20px |
| `--space-6` | 24px |
| `--space-8` | 32px |
| `--space-10` | 40px |
| `--space-12` | 48px |
| `--space-16` | 64px |

### 4.5 Border and Elevation

| Token | Value | Usage |
|-------|-------|-------|
| `--border-subtle` | `1px solid rgba(255,255,255,0.06)` | Card borders, dividers |
| `--border-default` | `1px solid rgba(255,255,255,0.10)` | Input fields, panels |
| `--border-strong` | `1px solid rgba(255,255,255,0.16)` | Active borders, focus rings |
| `--radius-sm` | `4px` | Buttons, badges |
| `--radius-md` | `8px` | Cards, panels |
| `--radius-lg` | `12px` | Modals, large containers |
| `--shadow-raised` | `0 2px 8px rgba(0,0,0,0.3)` | Cards |
| `--shadow-overlay` | `0 8px 32px rgba(0,0,0,0.5)` | Modals, dropdowns |

### 4.6 Iconography

Use Lucide React icons throughout the application. Lucide provides a consistent, clean icon set with good coverage of analytical and UI concepts. Icons should be rendered at 16px for inline use, 20px for navigation, and 24px for feature headers.

---

## 5. Page and View Specifications

### 5.1 Overview Dashboard (`/`)

**Purpose:** Provide a high-level summary of the entire dataset and offer multiple entry points into deeper analysis.

**Layout:** CSS Grid, 12-column layout

```
+-------------------------------------------------------------------+
|                        STATISTICS BAR                              |
|  [Documents: 12,847] [People: 1,234] [Orgs: 456] [Events: 2,891] |
|  [Relationships: 8,234] [Transactions: 1,567] [Media: 3,421]     |
+-------------------------------------------------------------------+
|                    |                          |                    |
|   MOST CONNECTED   |    RECENT EVENTS         |   AI INSIGHTS     |
|   PEOPLE           |    (mini-timeline)       |   FEED            |
|   (ranked list     |                          |   (scrollable     |
|    with sparklines)|                          |    card list)     |
|                    |                          |                    |
+--------------------+--------------------------+--------------------+
|                                   |                                |
|   FINANCIAL SUMMARY               |   GEOGRAPHIC HEATMAP           |
|   (top flows, total amounts,     |   (mini-map with location      |
|    anomaly flags)                |    density markers)            |
|                                   |                                |
+-----------------------------------+--------------------------------+
|                                                                    |
|   EXTRACTION STATUS                                                |
|   (progress bars showing extraction coverage and confidence)       |
+--------------------------------------------------------------------+
```

**Statistics Bar Specifications:**
- Horizontal row of stat cards, each 140px wide
- Each card shows: icon, count (large number), label (small text), and a micro trend indicator (up/down arrow with percentage change if applicable)
- Cards are clickable, navigating to the corresponding entity list

**Most Connected People Panel:**
- Ordered list of top 15 people by connection count
- Each row shows: rank number, name, connection count, primary role badge
- Clicking a name opens the context panel
- Sparkline beside each name showing their event frequency over time

**Recent Events Panel:**
- Vertical mini-timeline showing the 20 most recent events
- Each event shows: date, title, type badge, participant count
- Events are clickable

**AI Insights Feed:**
- Scrollable list of AI-generated insight cards
- Each card has: insight type icon, title, description (2 lines), confidence badge, timestamp
- Insight types: "New Connection Detected", "Financial Anomaly", "Temporal Cluster", "Missing Link Suggestion"
- Cards are dismissible or pinnable

### 5.2 People Directory (`/people`)

**Purpose:** Browse, search, and filter all individuals in the database.

**Layout:**

```
+-------------------------------------------------------------------+
|  PEOPLE                                        [View: Grid | List] |
|  [Search people...]  [Role Filter v] [Confidence v] [Sort v]      |
+-------------------------------------------------------------------+
|                                                                    |
|  +----------+  +----------+  +----------+  +----------+           |
|  | PERSON   |  | PERSON   |  | PERSON   |  | PERSON   |           |
|  | CARD     |  | CARD     |  | CARD     |  | CARD     |           |
|  |          |  |          |  |          |  |          |           |
|  | Name     |  | Name     |  | Name     |  | Name     |           |
|  | Role     |  | Role     |  | Role     |  | Role     |           |
|  | 23 conn  |  | 15 conn  |  | 8 conn   |  | 45 conn  |           |
|  | [Pin]    |  | [Pin]    |  | [Pin]    |  | [Pin]    |           |
|  +----------+  +----------+  +----------+  +----------+           |
|                                                                    |
|  (Virtualized grid, loads more on scroll)                         |
+-------------------------------------------------------------------+
```

**Person Card (Grid View):**
- 200px x 220px card
- Top section: avatar placeholder (initials on colored circle based on name hash)
- Name (truncated with tooltip if long)
- Primary role badge
- Connection count with small icon
- Document mention count
- Confidence level indicator (colored dot)
- Pin/bookmark button (top-right corner)
- Click opens context panel; double-click navigates to full profile

**Person Card (List View):**
- Single row, full width
- Columns: Name, Primary Role, Connections, Documents Mentioned In, Events, Confidence, First Seen Date, Actions

**Filters:**
- Role dropdown: All, Attorney, Associate, Employee, Victim, Government Official, etc.
- Confidence dropdown: All, High, Medium, Low
- Sort options: Name (A-Z), Connection Count (high to low), First Mentioned Date (newest/oldest)
- Redacted toggle: Show/Hide redacted individuals

### 5.3 Person Detail (`/people/:id`)

**Purpose:** Complete profile for an individual showing all related data.

**Layout:**

```
+-------------------------------------------------------------------+
|  <- Back to People                                                 |
|                                                                    |
|  [Avatar]  FULL NAME                          [Pin] [Add to Board] |
|            Primary Role | Confidence: High                        |
|            DOB: 1953-01-20 | Nationality: American                |
|            Victim ID: --- | Redacted: No                          |
+-------------------------------------------------------------------+
|  [Overview] [Relationships] [Events] [Financial] [Documents]       |
|  [Communications] [Media] [Notes]                                  |
+-------------------------------------------------------------------+
|                                                                    |
|  TAB CONTENT AREA (varies by selected tab)                        |
|                                                                    |
+-------------------------------------------------------------------+
```

**Overview Tab:**
- Summary statistics row: X relationships, Y events, Z documents, W transactions
- Known aliases and name variations list
- Contact information (email, phone, addresses) with copy-to-clipboard
- Associated organizations list
- AI-generated summary paragraph (if available)
- Notes section (user-editable)

**Relationships Tab:**
- Two views: List and Graph
- List view: table with columns (Connected Person, Relationship Type, Confidence, Date Range, Source Document)
- Graph view: ego-centric network graph centered on this person, showing 1-2 degrees of separation
- Relationship type filter checkboxes
- Confidence filter slider

**Events Tab:**
- Vertical timeline specific to this person
- Each event shows: date, title, type, location, other participants
- Filter by event type, date range

**Financial Tab:**
- Summary: total inbound, total outbound, net flow
- Transaction list: date, amount, currency, from/to, purpose, source document
- Mini Sankey showing money flow to/from this person

**Documents Tab:**
- List of all documents mentioning this person
- Each entry: EFTA number, title, date, document type, relevance snippet

**Communications Tab:**
- List of all communications sent by or received by this person
- Columns: date, type, subject, sender, recipients, has attachments
- Click to view full communication

**Media Tab:**
- Grid of media files where this person appears
- Each thumbnail shows the media file with the person's bounding box highlighted
- Confidence score overlay
- Identification method badge (AI, manual, verified)

### 5.4 Network Graph (`/network`)

**Purpose:** Interactive visualization of the relationship network between all people and organizations.

**Layout:**

```
+-------------------------------------------------------------------+
|  NETWORK GRAPH                                                     |
|  [Search node...] [Type Filter v] [Confidence v] [Layout v]       |
+-------------------------------------------------------------------+
|  +-------------------+  +---------------------------------------+ |
|  |                   |  |                                       | |
|  |  LEGEND           |  |                                       | |
|  |  -- Person        |  |        FORCE-DIRECTED GRAPH           | |
|  |  -- Org           |  |                                       | |
|  |  -- Associate     |  |     (Full remaining viewport)         | |
|  |  -- Financial     |  |                                       | |
|  |  -- Legal         |  |                                       | |
|  |  -- Employment    |  |                                       | |
|  |                   |  |                                       | |
|  | CONTROLS          |  |                                       | |
|  | [Zoom +/-]        |  |                                       | |
|  | [Fit all]         |  |                                       | |
|  | [Center on...]    |  |                                       | |
|  | [Degree: 1-2-3]   |  |                                       | |
|  | [# Connections]   |  |                                       | |
|  +-------------------+  +---------------------------------------+ |
+-------------------------------------------------------------------+
```

**Graph Specifications:**
- **Nodes:** Circular, sized by connection count (min 12px, max 48px radius)
  - People nodes: solid fill using `--accent-blue`
  - Organization nodes: rounded rectangle using `--accent-emerald`
  - Selected node: bright border ring with pulsing animation
  - Hovered node: enlarged with tooltip showing name and connection count
- **Edges:** Lines between connected nodes
  - Color encoded by relationship type
  - Width encoded by confidence level (thin = low, thick = high)
  - Dashed for low-confidence relationships
  - Hover reveals relationship type label
- **Interactions:**
  - Click node: select it, highlight its direct connections, dim others
  - Double-click node: open context panel
  - Click edge: show relationship details in a tooltip
  - Drag node: reposition it (physics simulation adjusts)
  - Scroll: zoom in/out
  - Pan: click and drag on empty space
  - Right-click node: context menu (View Profile, Pin, Add to Board, Find Path To...)
- **Find Path Feature:** Select two nodes, the system highlights the shortest path between them with degree count
- **Layout Options:** Force-directed (default), hierarchical, circular, radial from selected node
- **Performance:** For graphs with more than 500 nodes, enable progressive rendering with level-of-detail clustering

### 5.5 Event Timeline (`/timeline`)

**Purpose:** Chronological visualization of all events with filtering and drill-down.

**Layout:**

```
+-------------------------------------------------------------------+
|  TIMELINE                                                          |
|  [Date Range: |1990-01-01| to |2025-12-31|]                      |
|  [Type Filter v] [Person Filter v] [Location Filter v]            |
+-------------------------------------------------------------------+
|                                                                    |
|  1992 ---|------*------*----|----*----|--- 1993                    |
|          |      |      |    |    |    |                            |
|          |  Meeting  Flight | Court  |                             |
|          |  NYC     Palm B  | SDNY   |                             |
|                                                                    |
|  +------+ +--------+ +-------+ +------+ +--------+               |
|  |Event | |Event   | |Event  | |Event | |Event   |               |
|  |Card  | |Card    | |Card   | |Card  | |Card    |               |
|  |      | |        | |       | |      | |        |               |
|  +------+ +--------+ +-------+ +------+ +--------+               |
|                                                                    |
|  (Horizontal scrollable timeline with zoomable axis)              |
+-------------------------------------------------------------------+
```

**Timeline Specifications:**
- **Axis:** Horizontal time axis with adaptive scale (years, months, weeks, days depending on zoom level)
- **Zoom controls:** Mouse wheel zoom, pinch zoom on touch devices, zoom slider
- **Event markers:** Positioned on the axis line, colored by event type
  - Meeting: blue circle
  - Flight: purple triangle
  - Court hearing: red diamond
  - Transaction: amber square
  - Communication: purple pentagon
  - Custom: gray circle
- **Event cards:** Appear below the timeline when zoomed in enough to show detail
  - Title, date, type badge, location, participant count
  - Click to expand or open context panel
- **Clustering:** When events are too dense at the current zoom level, cluster them into a numbered group marker. Click to zoom into the cluster.
- **Brushing:** Click and drag on the timeline axis to select a date range. All other views can be linked to this selection.
- **Swimlanes mode:** Toggle to show events grouped by person or by event type in parallel horizontal lanes
- **Verification status:** Unverified events shown with a dashed outline

### 5.6 Financial Flow Analysis (`/financial`)

**Purpose:** Visualize and analyze money flows between people and organizations.

**Layout:**

```
+-------------------------------------------------------------------+
|  FINANCIAL FLOWS                                                   |
|  [Date Range] [Currency v] [Min Amount v] [Person/Org Filter]     |
+-------------------------------------------------------------------+
|  +-----------------------+  +-----------------------------------+ |
|  |                       |  |                                   | |
|  |  SUMMARY STATS        |  |        SANKEY DIAGRAM             | |
|  |                       |  |                                   | |
|  |  Total Volume: $X.XM  |  |  (Left: Sources)                 | |
|  |  # Transactions: NNN  |  |  (Right: Destinations)           | |
|  |  Unique Parties: NN   |  |  (Flows proportional to amount)  | |
|  |  Date Range: X to Y   |  |                                   | |
|  |  Avg Transaction: $XX |  |                                   | |
|  |                       |  |                                   | |
|  |  ANOMALIES            |  |                                   | |
|  |  [!] Unusual amount   |  |                                   | |
|  |  [!] Round numbers    |  |                                   | |
|  |  [!] Rapid succession |  |                                   | |
|  +-----------------------+  +-----------------------------------+ |
+-------------------------------------------------------------------+
|                                                                    |
|  TRANSACTION TABLE                                                 |
|  [Date] [Amount] [Currency] [From] [To] [Type] [Purpose] [Source] |
|  ---------------------------------------------------------------- |
|  2002-03-15  $50,000  USD  Person A  Org B  Wire  Legal fees  D1  |
|  2002-03-16  $125,000  USD  Org C  Person A  Wire  Investment  D2 |
|  ...                                                               |
+-------------------------------------------------------------------+
```

**Sankey Diagram Specifications:**
- Left column: source parties (senders)
- Right column: destination parties (receivers)
- Flows: width proportional to total amount transferred
- Color: each party gets a consistent color (hash of name)
- Hover on flow: tooltip showing total amount, transaction count, date range
- Click on flow: filter transaction table to those specific transactions
- Click on node: filter to all transactions involving that party
- The diagram should support 2-level nesting: Person within Organization

**Transaction Table:**
- Sortable by all columns
- Filterable by type, currency, amount range
- Click on From/To names to open context panel
- Click on Source document link to open document viewer
- Amount formatting with currency symbol and thousand separators
- Negative amounts (outflows) shown in red, inflows in green

### 5.7 Document Viewer (`/documents`)

**Purpose:** Browse, search, and read the full text of source documents.

**Layout:**

```
+-------------------------------------------------------------------+
|  DOCUMENTS                                                         |
|  [Full-text search...                                    ] [Go]   |
|  [Type v] [Date Range] [Status v] [Redacted v] [Sort v]          |
+-------------------------------------------------------------------+
|  +--------------------+  +--------------------------------------+ |
|  |                    |  |                                      | |
|  |  DOCUMENT LIST     |  |         DOCUMENT VIEWER              | |
|  |                    |  |                                      | |
|  |  EFTA00068050      |  |  EFTA00068050                       | |
|  |  > Letter re:...   |  |  Type: Letter | Date: 2003-04-12    | |
|  |  > 2003-04-12      |  |  Author: John Doe                  | |
|  |  > 95% confidence  |  |  Pages: 3 | 12,847 bytes            | |
|  |                    |  |  Confidence: 95%                    | |
|  |  EFTA00068051      |  |  ---------------------------------- | |
|  |  > Email corr...   |  |                                      | |
|  |  > 2003-04-13      |  |  [Full document text displayed here  | |
|  |  > 87% confidence  |  |   with entity highlights:            | |
|  |                    |  |   - People names in blue underline   | |
|  |  EFTA00068052      |  |   - Orgs in green underline          | |
|  |  > Financial...    |  |   - Locations in cyan underline      | |
|  |  > 2003-04-14      |  |   - Dates in amber underline         | |
|  |  > 92% confidence  |  |   - Amounts in red underline]        | |
|  |                    |  |                                      | |
|  |  (Virtualized list |  |  [Extracted Entities sidebar]        | |
|  |   with infinite    |  |  People: John Doe, Jane Smith        | |
|  |   scroll)          |  |  Orgs: Acme Corp                     | |
|  +--------------------+  +--------------------------------------+ |
+-------------------------------------------------------------------+
```

**Document List Panel (left, 320px wide):**
- Each entry shows: EFTA number (monospace), title (truncated), date, confidence badge
- Active document highlighted with accent border
- Full-text search results show matching snippet below each entry
- Search hit count per document
- Keyboard navigation: arrow keys to move between documents

**Document Viewer Panel (right, remaining width):**
- Header with document metadata: EFTA number, type, date, author, recipient, subject, page count, file size, confidence
- Full text content area with comfortable reading line length (max 720px, centered)
- Entity highlighting in the text:
  - People names: blue underline, clickable to open context panel
  - Organization names: green underline
  - Location names: cyan underline
  - Date references: amber underline
  - Financial amounts: red underline
- Toggle entity highlighting on/off
- Extracted entities sidebar (collapsible, right edge): lists all entities found in this document grouped by type
- Text zoom controls
- Copy text button
- Link to original PDF if available

### 5.8 Media Gallery (`/media`)

**Purpose:** Browse media files with AI analysis results, person identification, and EXIF metadata.

**Layout:**

```
+-------------------------------------------------------------------+
|  MEDIA GALLERY                                                     |
|  [Search...] [Type v] [Has Faces v] [Location v] [Date Range]    |
|  [View: Grid | Detail]                                            |
+-------------------------------------------------------------------+
|                                                                    |
|  +--------+  +--------+  +--------+  +--------+  +--------+      |
|  |        |  |        |  |        |  |        |  |        |      |
|  | Image  |  | Image  |  | Image  |  | Image  |  | Image  |      |
|  | thumb  |  | thumb  |  | thumb  |  | thumb  |  | thumb  |      |
|  |        |  |        |  |        |  |        |  |        |      |
|  | [2 ppl]|  | [GPS]  |  | [text] |  | [0 ppl]|  | [3 ppl]|      |
|  +--------+  +--------+  +--------+  +--------+  +--------+      |
|                                                                    |
|  (Masonry or grid layout, virtualized)                            |
+-------------------------------------------------------------------+
```

**Grid View:**
- Responsive grid of thumbnail cards (200px x 200px default)
- Each thumbnail shows:
  - Image preview with lazy loading
  - Bottom overlay bar with: face count badge, GPS indicator, text indicator
  - Hover reveals: filename, date taken, dimensions
  - Sensitive/explicit content blurred by default with click-to-reveal

**Detail View (single media file):**

```
+-------------------------------------------------------------------+
|  <- Back to Gallery                           [Prev] [Next]        |
+-------------------------------------------------------------------+
|  +-------------------------------+  +---------------------------+ |
|  |                               |  |  METADATA                 | |
|  |      IMAGE DISPLAY            |  |  File: photo_001.jpg      | |
|  |      (full resolution,       |  |  Format: JPEG              | |
|  |       zoomable, pannable)    |  |  Size: 2.4 MB             | |
|  |                               |  |  Dimensions: 3024x4032   | |
|  |  [Bounding boxes shown       |  |  Date Taken: 2003-07-14   | |
|  |   around detected faces      |  |  Camera: Canon EOS 5D     | |
|  |   and objects with labels]   |  |  GPS: 18.3358, -64.9310   | |
|  |                               |  |                           | |
|  +-------------------------------+  |  AI ANALYSIS              | |
|                                      |  Caption: "Three people   | |
|                                      |   standing on a yacht..."| |
|                                      |  Scene: Outdoor/Marine   | |
|                                      |  Tags: yacht, ocean,     | |
|                                      |   sunlight               | |
|                                      |  Confidence: 92%         | |
|                                      |                           | |
|                                      |  IDENTIFIED PEOPLE        | |
|                                      |  [1] Person A (95%)      | |
|                                      |  [2] Person B (78%)      | |
|                                      |  [3] Unknown (--%)       | |
|                                      |                           | |
|                                      |  LINKED EVENTS            | |
|                                      |  Event: Yacht trip 2003  | |
|                                      +---------------------------+ |
+-------------------------------------------------------------------+
```

**Image Display:**
- Renders the image at maximum visible resolution
- Pan and zoom with mouse/trackpad
- Bounding boxes overlaid on detected faces and objects
- Bounding boxes color-coded: identified person (blue), unidentified face (amber), object (gray)
- Click on bounding box to see identification details
- Toggle bounding box visibility

### 5.9 Map View (`/map`)

**Purpose:** Geographic visualization of all locations, events, and media with GPS coordinates.

**Layout:**

```
+-------------------------------------------------------------------+
|  MAP                                                               |
|  [Search location...] [Layer: Events | Media | Properties | All]  |
+-------------------------------------------------------------------+
|  +-------------------+                                             |
|  |                   |                                             |
|  |  LAYER CONTROLS   |         FULL-VIEWPORT MAP                  |
|  |                   |                                             |
|  |  [x] Events       |         (Dark-themed Leaflet map with      |
|  |  [x] Media GPS    |          CartoDB dark basemap tiles)       |
|  |  [x] Properties   |                                             |
|  |  [x] Addresses    |                                             |
|  |                   |                                             |
|  |  LOCATION LIST    |         Markers clustered at zoom levels    |
|  |  (scrollable)     |         below threshold. Spiderfied on     |
|  |                   |         click at close zoom.                |
|  |  > New York, NY   |                                             |
|  |  > Palm Beach, FL |                                             |
|  |  > London, UK     |                                             |
|  |  > St. Thomas, VI |                                             |
|  +-------------------+                                             |
+-------------------------------------------------------------------+
```

**Map Specifications:**
- **Basemap:** CartoDB Dark Matter tiles (`dark_all` variant)
- **Marker types:**
  - Location pins: standard pin icon, colored by location type (property = cyan, office = emerald, residence = blue)
  - Event markers: pulsing circle at event location, sized by participant count
  - Media markers: camera icon at GPS coordinates of photos
  - All markers clustered using Supercluster for performance
- **Popup on click:** Shows location name, type, address, owner, linked events count, linked media count
- **Interactions:**
  - Click marker: show popup
  - Click location name in popup: open context panel
  - Click cluster: zoom to expand
  - Draw rectangle: select all markers within area
- **Layer control panel:** Left side, 240px wide, showing toggleable layers and a scrollable list of all locations

### 5.10 Communications View (`/communications`)

**Purpose:** Analyze email, letter, and phone call patterns between individuals.

**Layout:**

```
+-------------------------------------------------------------------+
|  COMMUNICATIONS                                                    |
|  [Search...] [Type v] [Date Range] [Person v] [Has Attachments v] |
+-------------------------------------------------------------------+
|  +--------------------+  +--------------------------------------+ |
|  |                    |  |                                      | |
|  |  COMMUNICATION     |  |       COMMUNICATION DETAIL           | |
|  |  LIST              |  |                                      | |
|  |                    |  |  Type: Email | Date: 2003-04-12      | |
|  |  [Email icon]      |  |  From: Person A                     | |
|  |  Subject line...   |  |  To: Person B, Person C             | |
|  |  From: Person A    |  |  CC: Person D                       | |
|  |  2003-04-12        |  |  Subject: Re: Meeting arrangement   | |
|  |  ---               |  |  Attachments: 2                     | |
|  |  [Letter icon]     |  |  ---------------------------------- | |
|  |  Subject line...   |  |                                      | |
|  |  From: Person B    |  |  [Full body text of communication    | |
|  |  2003-04-13        |  |   with entity highlighting]          | |
|  |  ---               |  |                                      | |
|  |                    |  |  Source Document: EFTA00068050       | |
|  +--------------------+  +--------------------------------------+ |
+-------------------------------------------------------------------+
```

**Communication List:**
- Each entry shows: type icon (email/letter/phone/fax), subject (truncated), sender name, date, attachment indicator
- Grouped by conversation thread when possible
- Search highlights in subject and body preview

**Communication Detail:**
- Full header: type, date, time, sender (clickable), recipients list (each clickable), CC/BCC
- Body text with entity highlighting (same as document viewer)
- Attachment list with file type icons
- Source document link
- Related communications (same thread or same participants within +/- 7 days)

### 5.11 Evidence View (`/evidence`)

**Purpose:** Track physical evidence items with chain of custody information.

**Layout:** Standard list/detail split view similar to documents.

**Evidence Card:**
- Evidence number, type badge, description
- Seizure information: from whom, from where, when
- Current location and status
- Chain of custody timeline
- Linked media files
- Source document reference

### 5.12 Investigation Boards (`/boards`)

**Purpose:** User-created canvases for organizing hypotheses, pinning evidence, and annotating connections. This is the "digital cork board."

**Layout:**

```
+-------------------------------------------------------------------+
|  INVESTIGATION BOARDS                                              |
|  [+ New Board] [My Boards v]                                      |
+-------------------------------------------------------------------+
|  +-------+  +-------+  +-------+  +-------+                      |
|  | Board |  | Board |  | Board |  | Board |                      |
|  | Card  |  | Card  |  | Card  |  | Card  |                      |
|  |       |  |       |  |       |  |       |                      |
|  | Name  |  | Name  |  | Name  |  | Name  |                      |
|  | Items |  | Items |  | Items |  | Items |                      |
|  | Date  |  | Date  |  | Date  |  | Date  |                      |
|  +-------+  +-------+  +-------+  +-------+                      |
+-------------------------------------------------------------------+
```

**Board Detail View (individual board):**

```
+-------------------------------------------------------------------+
|  <- Boards    Board Name: [editable]           [Share] [Export]    |
+-------------------------------------------------------------------+
|                                                                    |
|  +----------+    +----------+                                      |
|  | PINNED   |    | PINNED   |        FREE-FORM CANVAS             |
|  | PERSON   |    | DOCUMENT |        (infinite scroll area)       |
|  | CARD     |    | CARD     |                                      |
|  +----+-----+    +-----+----+        Users can:                   |
|       |                |             - Drag items from any view    |
|       +---[red line]---+             - Draw connector lines        |
|                                      - Add text annotations       |
|  +---------+                         - Group items in regions     |
|  | STICKY  |                         - Color-code connections     |
|  | NOTE    |    +----------+         - Add sticky notes           |
|  | "Check  |    | PINNED   |                                      |
|  |  the    |    | EVENT    |                                      |
|  |  dates" |    | CARD     |                                      |
|  +---------+    +----------+                                      |
|                                                                    |
+-------------------------------------------------------------------+
```

**Board Canvas Specifications:**
- Infinite canvas with pan and zoom
- Items can be placed freely via drag-and-drop
- Item types that can be placed:
  - Pinned entity cards (person, org, event, document, media, transaction)
  - Sticky notes (user-created text blocks with color selection)
  - Connector lines between items (straight or curved, color-selectable)
  - Freehand annotations
  - Group regions (colored rectangles used to visually group items)
- Items show a compact card version on the board with click-to-expand
- Right-click context menu on items: Remove from Board, View Full Detail, Change Color, Add Note
- Board state persisted to local storage (or companion SQLite table)
- Export board as image (PNG/SVG) or as structured JSON

### 5.13 Bookmarks / Pinned Items (`/bookmarks`)

**Purpose:** Quick-access list of items the user has pinned from any view.

**Layout:**

```
+-------------------------------------------------------------------+
|  BOOKMARKS                                                         |
|  [Filter by type v] [Sort: Date Added | Name | Type]             |
+-------------------------------------------------------------------+
|  +-------+  +-------+  +-------+  +-------+  +-------+          |
|  |People |  |Docs   |  |Events |  |Fin.   |  |Media  |          |
|  |  (12) |  |  (8)  |  |  (5)  |  |  (3)  |  |  (7)  |          |
|  +-------+  +-------+  +-------+  +-------+  +-------+          |
|                                                                    |
|  TYPE: People                                                      |
|  ---------------------------------------------------------------- |
|  [x] Person A          | Associate   | Pinned 2h ago   | [Unpin] |
|  [x] Person B          | Attorney    | Pinned 1d ago   | [Unpin] |
|  ...                                                               |
|  TYPE: Documents                                                   |
|  ---------------------------------------------------------------- |
|  [x] EFTA00068050      | Letter      | Pinned 3h ago   | [Unpin] |
|  ...                                                               |
+-------------------------------------------------------------------+
```

- Grouped by entity type with count badges
- Each entry shows: name/identifier, type, time since pinned, unpin action
- Click on entry opens context panel
- Bulk actions: unpin selected, add selected to board

### 5.14 AI Insights (`/ai-insights`)

**Purpose:** Dedicated view for AI-generated analysis, pattern detection, and suggested connections.

See Section 9 for detailed AI feature workflows.

### 5.15 Settings (`/settings`)

**Purpose:** Application configuration.

**Sections:**
- **Display:** Theme selection (dark/light/auto), font size adjustment, default view preferences
- **Data:** Database path configuration, re-index triggers, extraction status overview
- **Export:** Default export format, include confidence scores toggle
- **AI:** AI provider configuration (API endpoint, model selection), analysis batch size
- **About:** Application version, database statistics, last extraction date

---

## 6. Component Inventory

### 6.1 Layout Components

| Component | Description | Props |
|-----------|-------------|-------|
| `AppShell` | Root layout with top bar, sidebar, and content area | `children` |
| `TopBar` | Global search, pin count, help button | `onSearch`, `pinCount` |
| `SideNav` | Icon rail navigation with expand-on-hover | `activeRoute`, `onNavigate` |
| `ContentArea` | Main content wrapper with scroll management | `children` |
| `ContextPanel` | Right slide-out detail panel | `entity`, `isOpen`, `onClose` |
| `Breadcrumb` | Navigation breadcrumb trail | `items` |
| `SplitPane` | Resizable left/right split layout | `leftContent`, `rightContent`, `defaultSplit` |

### 6.2 Data Display Components

| Component | Description | Props |
|-----------|-------------|-------|
| `EntityCard` | Compact card for any entity type | `entity`, `type`, `onPin`, `onClick` |
| `PersonCard` | Person-specific card with avatar and stats | `person`, `variant: 'grid' \| 'list'` |
| `DocumentCard` | Document entry with EFTA number and metadata | `document`, `searchHighlight` |
| `EventCard` | Event entry with date, type, participants | `event`, `compact` |
| `TransactionRow` | Financial transaction table row | `transaction` |
| `MediaThumbnail` | Media file thumbnail with overlay badges | `media`, `showBoundingBoxes` |
| `CommunicationCard` | Communication entry with type icon and preview | `communication` |
| `EvidenceCard` | Evidence item with chain of custody | `evidence` |
| `StatCard` | Numeric statistic with icon, label, and trend | `icon`, `value`, `label`, `trend` |
| `ConfidenceBadge` | Colored dot/label for confidence level | `level: 'high' \| 'medium' \| 'low'` |
| `TypeBadge` | Colored badge for entity or event type | `type`, `colorMap` |
| `InsightCard` | AI insight with type, title, and action | `insight`, `onDismiss`, `onPin` |

### 6.3 Visualization Components

| Component | Description | Props |
|-----------|-------------|-------|
| `NetworkGraph` | Force-directed relationship graph | `nodes`, `edges`, `onNodeClick`, `layout` |
| `Timeline` | Horizontal interactive timeline | `events`, `dateRange`, `onBrush`, `onEventClick` |
| `SankeyDiagram` | Financial flow Sankey chart | `transactions`, `onFlowClick`, `onNodeClick` |
| `MapView` | Leaflet map with clustered markers | `locations`, `layers`, `onMarkerClick` |
| `InvestigationCanvas` | Infinite drag-and-drop canvas | `items`, `connectors`, `onItemAdd`, `onSave` |
| `MiniTimeline` | Compact timeline for sidebars | `events`, `height` |
| `MiniMap` | Compact map for dashboard | `locations`, `height` |
| `Sparkline` | Inline trend line | `data`, `width`, `height`, `color` |

### 6.4 Input and Filter Components

| Component | Description | Props |
|-----------|-------------|-------|
| `GlobalSearch` | Universal search with categorized results | `onSearch`, `recentSearches` |
| `FilterBar` | Horizontal bar of filter dropdowns | `filters`, `activeFilters`, `onChange` |
| `DateRangePicker` | Start/end date selection | `value`, `onChange`, `min`, `max` |
| `ConfidenceFilter` | Dropdown or slider for confidence level | `value`, `onChange` |
| `TypeFilter` | Multi-select for entity/event types | `options`, `selected`, `onChange` |
| `SortControl` | Sort direction and field selector | `options`, `activeSort`, `onChange` |
| `SearchHighlight` | Renders text with search term highlighting | `text`, `searchTerms` |

### 6.5 Feedback and Utility Components

| Component | Description | Props |
|-----------|-------------|-------|
| `LoadingSpinner` | Centered loading indicator | `size`, `label` |
| `EmptyState` | Shown when no data matches filters | `icon`, `title`, `description`, `action` |
| `ErrorBoundary` | Error catching with retry option | `fallback`, `onRetry` |
| `Tooltip` | Informational hover tooltip | `content`, `placement` |
| `Toast` | Notification toast message | `message`, `type`, `duration` |
| `ConfirmDialog` | Confirmation modal for destructive actions | `title`, `message`, `onConfirm`, `onCancel` |
| `KeyboardShortcutHelp` | Modal listing all keyboard shortcuts | `isOpen`, `onClose` |

---

## 7. Interaction Patterns

### 7.1 Entity Selection and Cross-Referencing

The core interaction pattern is: **click any entity reference anywhere in the application to open its context panel without losing your current view.** This enables fluid cross-referencing.

- Clicking a person name in a document opens their profile in the context panel
- Clicking a location in an event opens the location in the context panel with a mini-map
- Clicking a document reference in a transaction opens the document in the context panel
- The context panel supports internal navigation (e.g., switching tabs) without closing

### 7.2 Pin and Board Workflow

**Pinning:** Every entity card and every context panel has a pin button (bookmark icon). Pinning adds the entity to the bookmarks list and increments the pin count in the top bar. Pinned items have a visible indicator (filled bookmark icon) wherever they appear.

**Adding to Board:** Every entity card and context panel has an "Add to Board" button. Clicking it shows a dropdown of existing boards plus a "New Board" option. After selecting a board, the entity is placed at the next available position on the canvas. A toast confirms the action.

### 7.3 Keyboard Navigation

| Shortcut | Action |
|----------|--------|
| `/` or `Ctrl+K` | Focus global search |
| `Escape` | Close context panel, close modals, clear search |
| `1-9` | Navigate to view by position (1=Overview, 2=People, etc.) |
| `P` | Pin/unpin currently selected entity |
| `B` | Add currently selected entity to board |
| `Left/Right arrows` | Navigate between items in lists |
| `Enter` | Open selected item |
| `Ctrl+E` | Export current view |
| `?` | Show keyboard shortcuts help |

### 7.4 Drag and Drop

- Drag entity cards from any list onto an investigation board (cross-view drag)
- Drag items on investigation board canvas to reposition them
- Drag timeline handles to adjust date range
- Drag split pane dividers to resize panels

### 7.5 Right-Click Context Menus

Right-clicking on any entity provides a context menu with these standard actions:

| Action | Description |
|--------|-------------|
| View Full Detail | Navigate to the entity's detail page |
| Open in Context Panel | Show summary in the right panel |
| Pin / Unpin | Toggle bookmark status |
| Add to Board | Add to an investigation board |
| Copy Link | Copy a deep link URL to clipboard |
| Find Connections | Open network graph centered on this entity |
| View on Timeline | Show this entity's events on the timeline |
| View on Map | Show this entity's locations on the map |

### 7.6 Linked Brushing Across Views

When a user selects a date range on the timeline, other views can optionally synchronize:

- The financial view filters to transactions within that date range
- The communications view filters to messages within that date range
- The network graph highlights relationships active during that period
- The map shows only events within that date range

This is an opt-in behavior toggled by a "Link Views" button in the top bar.

---

## 8. Data Visualization Specifications

### 8.1 Network Graph

**Library Recommendation:** Sigma.js with `@react-sigma` for rendering, Graphology for graph data structure. This combination provides WebGL rendering performance for large graphs with a clean React integration.

**Node Encoding:**

| Attribute | Visual Encoding |
|-----------|----------------|
| Entity type (person/org) | Shape (circle/rounded rectangle) |
| Connection count | Node size (logarithmic scale, 12px-48px) |
| Confidence level | Border style (solid/dashed) |
| Selected state | Bright border ring with glow effect |
| Pinned state | Small star overlay icon |

**Edge Encoding:**

| Attribute | Visual Encoding |
|-----------|----------------|
| Relationship type | Color (matching accent palette) |
| Confidence | Line width (1px low, 2px medium, 3px high) |
| Low confidence | Dashed line |
| Active/selected | Full opacity; others reduced to 20% |

**Performance Targets:**
- Up to 500 nodes: full detail rendering at 60fps
- 500-2000 nodes: reduced label rendering, cluster small communities
- 2000+ nodes: automatic level-of-detail with expand-on-zoom

### 8.2 Timeline

**Library Recommendation:** Custom implementation using D3.js `d3-time`, `d3-scale`, and `d3-axis` with React rendering. This provides the precise control needed for investigative timeline interactions.

**Scale Behavior:**

| Zoom Level | Axis Ticks | Event Display |
|------------|-----------|---------------|
| Decade view | Years | Clustered counts only |
| Year view | Months | Event type indicators |
| Month view | Weeks | Individual event markers |
| Week view | Days | Full event cards |
| Day view | Hours | Detailed event cards with times |

**Color Encoding for Event Types:**

| Event Type | Color | Marker Shape |
|------------|-------|-------------|
| Meeting | `#4A9EFF` (blue) | Circle |
| Flight | `#A78BFA` (purple) | Triangle (pointing right) |
| Court Hearing | `#F87171` (red) | Diamond |
| Transaction | `#FBBF24` (amber) | Square |
| Communication | `#A78BFA` (purple) | Pentagon |
| Employment | `#34D399` (emerald) | Hexagon |
| Other | `#6B6B7B` (gray) | Circle |

### 8.3 Sankey Diagram

**Library Recommendation:** D3.js with `d3-sankey` plugin, rendered in React. This provides maximum control over the financial flow visualization.

**Specifications:**
- Nodes sized by total flow volume (sum of inbound and outbound)
- Node labels show name and total volume
- Links colored by source node color with 40% opacity
- Hover on link: increase opacity to 80%, show tooltip with: amount, transaction count, date range, purpose breakdown
- Minimum link width: 2px (for visibility of small transactions)
- Maximum of 20 nodes visible at once; smaller flows aggregated into "Other" category
- Sort nodes by total flow volume, largest at top

### 8.4 Map

**Library Recommendation:** React Leaflet with CartoDB Dark Matter basemap tiles and Supercluster for marker clustering.

**Marker Specifications:**

| Marker Type | Icon | Size | Color |
|-------------|------|------|-------|
| Property/Residence | House icon | 24px | `#22D3EE` (cyan) |
| Office/Business | Building icon | 24px | `#34D399` (emerald) |
| Event location | Pulsing circle | 16-32px (by importance) | `#FBBF24` (amber) |
| Media GPS | Camera icon | 20px | `#FB923C` (orange) |
| Cluster | Circle with count | 32-48px | `#4A9EFF` (blue) |

**Popup Content:**
- Location name and type
- Street address
- Owner (if known, clickable)
- Events at this location (count, most recent)
- Media at this location (count, thumbnail strip)
- "View All" links to filtered views

### 8.5 Sparklines

Small inline trend visualizations used in the overview dashboard and entity cards.

**Specifications:**
- Width: 80px, Height: 24px
- No axes, no labels (purely visual trend)
- Line width: 1.5px
- Color: matches the entity accent color
- Fill: gradient from accent color (20% opacity) to transparent

---

## 9. AI Feature Workflows

### 9.1 AI Analysis Overview

The AI layer provides four categories of analysis. All AI features display their confidence scores and source reasoning so users can evaluate the quality of suggestions.

### 9.2 Entity Extraction Enhancement

**Trigger:** Automatic on document import, or manual "Re-analyze" button per document.

**Workflow:**
1. User navigates to a document in the document viewer
2. The extracted entities sidebar shows AI-identified entities with confidence scores
3. Each entity shows: extracted text span, entity type, confidence percentage, link to matched database record (if any)
4. Users can confirm, reject, or correct entity identifications
5. Rejected entities are grayed out; confirmed entities get a checkmark badge

**Display in UI:**
- Entity highlighting in document text uses underline with confidence-based opacity (high = solid, low = dotted)
- A "Re-analyze with AI" button triggers fresh extraction
- Results panel shows diff: "New entities found", "Existing entities confirmed", "Entities not found in re-analysis"

### 9.3 Connection Suggestion Engine

**Trigger:** Automatic background analysis, results appear in AI Insights feed.

**Workflow:**
1. The system analyzes co-occurrence patterns, temporal proximity, financial links, and communication patterns
2. Suggested connections appear as insight cards in the AI Insights view and on the overview dashboard
3. Each suggestion shows:
   - The two (or more) entities suggested to be connected
   - The type of suggested connection
   - The evidence supporting the suggestion (list of documents, events, or transactions)
   - A confidence score
   - "Accept" and "Dismiss" actions
4. Accepted suggestions can optionally be added to an investigation board

**Insight Card Layout:**
```
+-------------------------------------------------------+
|  [icon] CONNECTION SUGGESTED           [Dismiss] [Pin] |
|                                                        |
|  Person A may be connected to Organization B           |
|  Evidence: Mentioned together in 5 documents,          |
|  financial flow of $250,000 between 2002-2004          |
|                                                        |
|  Confidence: 78%     [View Evidence] [Accept]          |
+-------------------------------------------------------+
```

### 9.4 Financial Pattern Detection

**Trigger:** Available in the Financial view as an "Analyze Patterns" button.

**Detection Categories:**
- **Round number transactions:** Transactions with suspiciously round amounts (e.g., exactly $100,000)
- **Rapid succession:** Multiple transactions between the same parties within short time periods
- **Circular flows:** Money flowing from A to B to C and back to A
- **Unusual amounts:** Transactions significantly deviating from the typical range for that pair of parties
- **Structuring indicators:** Multiple transactions just below reporting thresholds

**Display:**
- Anomaly flags appear as warning badges on individual transactions in the transaction table
- A summary panel shows aggregate anomaly statistics
- Each anomaly is clickable to view the specific transactions and reasoning

### 9.5 Temporal Clustering Analysis

**Trigger:** Available in the Timeline view as an "Detect Clusters" button.

**Workflow:**
1. AI analyzes the temporal distribution of events
2. Identifies statistically significant clusters of activity
3. Highlights cluster periods on the timeline with a shaded background region
4. Each cluster shows: date range, event count, key participants, suggested significance
5. Users can drill into a cluster to see all events within it

### 9.6 AI Insights View (`/ai-insights`)

**Layout:**

```
+-------------------------------------------------------------------+
|  AI INSIGHTS                                                       |
|  [Run Full Analysis] [Filter: All | Connections | Financial |      |
|   Temporal | Entities]  [Sort: Confidence | Date | Type]          |
+-------------------------------------------------------------------+
|                                                                    |
|  NEW INSIGHTS (3)                                                 |
|  +------------------------------------------------------------+  |
|  | [CONNECTION] Person X linked to Org Y through 3 documents  |  |
|  | Confidence: 82%  |  Generated: 2h ago  |  [View] [Pin]     |  |
|  +------------------------------------------------------------+  |
|  +------------------------------------------------------------+  |
|  | [FINANCIAL] Unusual transaction pattern detected            |  |
|  | 12 transactions totaling $1.2M in 48-hour window           |  |
|  | Confidence: 91%  |  Generated: 3h ago  |  [View] [Pin]     |  |
|  +------------------------------------------------------------+  |
|                                                                    |
|  REVIEWED INSIGHTS (15)                                           |
|  (Previously viewed insights, lower visual emphasis)              |
+-------------------------------------------------------------------+
```

**Analysis Pipeline Display:**
When "Run Full Analysis" is clicked, show a progress modal:
```
+---------------------------------------+
|  AI ANALYSIS IN PROGRESS              |
|                                       |
|  [====------] Entity extraction  40%  |
|  [----------] Connection analysis  0% |
|  [----------] Financial patterns   0% |
|  [----------] Temporal clusters    0% |
|                                       |
|  Estimated time remaining: 2 min      |
|  [Cancel]                             |
+---------------------------------------+
```

---

## 10. Investigative Workflow Features

### 10.1 Annotation System

Every entity in the system supports user annotations. Annotations are stored separately from the source data.

**Annotation Types:**
- **Text notes:** Free-text notes attached to any entity
- **Tags:** User-defined tags (e.g., "key witness", "needs verification", "follow up")
- **Status flags:** Mark entities with investigative status (Investigating, Confirmed, Ruled Out, Follow Up)
- **Linked annotations:** Notes that reference multiple entities together

**UI for Annotations:**
- A "Notes" tab in every entity detail view and context panel
- Notes are timestamped and ordered chronologically
- Rich text editing with basic formatting (bold, italic, bullet lists)
- Tag input with autocomplete from existing tags

### 10.2 Export Functionality

**Export from any view:**
- **Entity lists:** Export filtered results as CSV, JSON, or formatted PDF
- **Network graph:** Export as PNG image, SVG, or graph data (GEXF format for Gephi)
- **Timeline:** Export as PNG image or CSV of events
- **Financial data:** Export transactions as CSV with all metadata
- **Investigation board:** Export as PNG image or structured JSON
- **Full investigation report:** Generate a structured document with selected bookmarks, annotations, and supporting evidence

**Export Dialog:**
```
+---------------------------------------+
|  EXPORT                               |
|                                       |
|  Format: [CSV v]                      |
|  Include: [x] Entity data             |
|           [x] Confidence scores       |
|           [ ] Source document refs     |
|           [x] User annotations        |
|                                       |
|  Scope: [Current filtered view v]     |
|                                       |
|  [Cancel]           [Export]          |
+---------------------------------------+
```

### 10.3 Cross-Reference Panel

When viewing any entity, a "Cross-Reference" action opens a special mode that highlights all connections to the current entity across all data types:

- Documents mentioning this entity
- Events involving this entity
- Financial transactions involving this entity
- Communications sent or received by this entity
- Media files featuring this entity
- Other entities connected to this entity

The cross-reference results are displayed as a tabbed panel below the entity detail, with counts on each tab.

---

## 11. Responsive Design Considerations

### 11.1 Design Philosophy for Screen Sizes

This application is primarily designed for desktop workstations with large screens (1920px and above). Analytical work requires screen real estate for side-by-side comparison, graph visualization, and document reading. However, the application should gracefully degrade for smaller screens.

### 11.2 Breakpoint Definitions

| Breakpoint | Range | Target Device | Layout Adjustments |
|------------|-------|---------------|-------------------|
| XL (primary) | 1440px+ | Desktop workstation | Full layout as designed |
| LG | 1024px - 1439px | Laptop | Context panel becomes full-page overlay; sidebar collapses to icon rail permanently |
| MD | 768px - 1023px | Tablet (landscape) | Single-column layout; split panes stack vertically; network graph and map become full-screen modal views |
| SM | < 768px | Tablet (portrait) / Phone | Minimal functionality; read-only entity browsing; no graph/map/board views; simplified navigation |

### 11.3 Layout Adaptations by Breakpoint

**XL (1440px+):**
- Full three-zone layout: sidebar + content + context panel
- Split pane views (document list + viewer)
- All visualizations at full resolution

**LG (1024px - 1439px):**
- Sidebar permanently collapsed to 64px icon rail
- Context panel opens as overlay (not side-by-side)
- Split panes default to 40/60 split instead of 30/70
- Visualization controls collapse to dropdown menus

**MD (768px - 1023px):**
- Bottom tab navigation replaces sidebar
- Split pane views stack vertically (list on top, detail below)
- Network graph, map, and timeline open in full-screen modal overlays
- Investigation boards are view-only (no editing)

**SM (< 768px):**
- Bottom tab navigation with 5 primary tabs only
- Simple list views for all entity types
- No graph, map, timeline, or board views
- Search and entity detail remain functional
- Banner message: "For full analysis capabilities, use a desktop browser"

---

## 12. Accessibility Requirements

### 12.1 WCAG 2.1 AA Compliance

The application must meet WCAG 2.1 Level AA standards. Given the dark theme, particular attention is required for contrast ratios.

### 12.2 Color Contrast

All text and interactive elements must meet these minimums against the dark background surfaces:

| Element Type | Minimum Contrast Ratio | Status |
|-------------|----------------------|--------|
| Normal text (14px regular) | 4.5:1 | Enforced by `--text-primary` (13.2:1), `--text-secondary` (7.1:1), `--text-tertiary` (4.5:1) |
| Large text (18px+ or 14px bold) | 3:1 | Enforced by all text tokens |
| UI components (buttons, inputs) | 3:1 | Enforced by `--border-strong` and accent colors |
| Graphical objects (chart elements) | 3:1 | Enforced by accent color palette |
| Focus indicators | 3:1 | 2px solid `--accent-blue` ring |

### 12.3 Non-Color Information Encoding

No information is conveyed by color alone. Every color-coded element has a secondary encoding:

| Data | Color Encoding | Secondary Encoding |
|------|---------------|-------------------|
| Confidence levels | Green/Amber/Red | Text label ("High", "Medium", "Low") + icon |
| Entity types | Different accent colors | Shape (in graph), icon, text label |
| Event types | Different colors | Shape (in timeline), text label, icon |
| Relationship types | Edge colors | Line style (solid/dashed) + hover label |
| Financial direction | Red (out) / Green (in) | Arrow direction icon + "+"/"-" prefix |

### 12.4 Keyboard Navigation

- All interactive elements are reachable via Tab key
- Focus indicators are clearly visible (2px solid ring in accent blue)
- Skip-to-content link available at page top
- All visualizations have keyboard alternatives:
  - Network graph: node list with arrow key navigation
  - Timeline: event list with arrow key navigation
  - Map: location list as alternative
  - Sankey: transaction table as alternative
- Modal dialogs trap focus
- Escape key closes any overlay/modal

### 12.5 Screen Reader Support

- All images have descriptive `alt` text
- Visualization components have `aria-label` descriptions summarizing the data
- Data tables use proper `<th>` headers with `scope` attributes
- Live regions (`aria-live`) for dynamic content updates (search results, AI insights)
- Navigation landmarks: `<nav>`, `<main>`, `<aside>`, `<header>`
- Headings follow proper hierarchy (h1 > h2 > h3, no skipping)

### 12.6 Motion and Animation

- Animations respect `prefers-reduced-motion` media query
- When reduced motion is preferred:
  - Graph layout transitions become instant
  - Timeline zoom transitions become step-based
  - Card hover effects are disabled
  - Loading spinners use a static progress bar instead
- No content auto-rotates or auto-scrolls

### 12.7 Text Scaling

- All text uses relative units (rem/em)
- Layout does not break at 200% zoom
- Text does not require horizontal scrolling at 200% zoom in single-column views

---

## 13. Performance Requirements

### 13.1 Load Time Targets

| Metric | Target |
|--------|--------|
| Initial page load (cold) | Under 3 seconds |
| Subsequent navigation | Under 500ms |
| Search results display | Under 200ms (with debounce) |
| Network graph render (500 nodes) | Under 1 second |
| Timeline render (1000 events) | Under 500ms |
| Map render with 500 markers | Under 1 second |
| Context panel open | Under 200ms |

### 13.2 Data Handling

- **Virtualized lists:** All entity lists use virtual scrolling (react-window or react-virtuoso) to handle thousands of entries
- **Pagination:** API queries paginated at 100 items per page with infinite scroll
- **Lazy loading:** Images and media thumbnails loaded only when visible in viewport
- **Indexed search:** Full-text search powered by SQLite FTS5 or a pre-built index
- **Caching:** Frequently accessed entities (people, locations) cached in memory with LRU eviction
- **Web Workers:** Heavy computations (graph layout, clustering) offloaded to Web Workers

### 13.3 Database Query Optimization

Since this reads from a SQLite database, the API layer should:
- Use prepared statements for all queries
- Implement connection pooling appropriate for SQLite (single-writer, multiple-reader)
- Create indexes on: `people.full_name`, `documents.efta_number`, `events.event_date`, `financial_transactions.transaction_date`, `relationships.person1_id`, `relationships.person2_id`
- Pre-compute relationship graph statistics at startup and cache

---

## 14. Recommended Technology Stack

### 14.1 Frontend

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Framework | React 18+ with TypeScript | Required by project spec |
| Routing | React Router v6 | Standard for React SPAs |
| State Management | Zustand or Jotai | Lightweight, minimal boilerplate, good for analytical dashboards |
| Styling | Tailwind CSS + CSS custom properties | Utility-first with design token support; fast iteration |
| Icons | Lucide React | Comprehensive, consistent, tree-shakeable |
| Network Graph | Sigma.js + @react-sigma + Graphology | WebGL rendering, scales to thousands of nodes |
| Timeline | Custom D3.js + React | Maximum control over investigative timeline UX |
| Sankey | D3.js + d3-sankey | Best open-source option for financial flows |
| Map | React Leaflet + Supercluster | Open source, dark tiles support, clustering |
| Charts | Recharts or Nivo | For sparklines and summary statistics |
| Virtual Scrolling | react-virtuoso | Handles large lists with variable heights |
| Drag and Drop | @dnd-kit | Modern, accessible drag-and-drop for boards |
| Rich Text | TipTap | For annotation notes editor |
| Date Handling | date-fns | Lightweight date manipulation |
| Data Fetching | TanStack Query (React Query) | Caching, pagination, background refetching |

### 14.2 Backend API

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Runtime | Node.js or Bun | Self-hosted, simple setup |
| Framework | Express.js or Fastify | Lightweight REST API over SQLite |
| Database | better-sqlite3 | Synchronous SQLite bindings, best performance for reads |
| ORM | Drizzle ORM or raw SQL | Type-safe queries with minimal overhead |
| Search | SQLite FTS5 | Built-in full-text search, no external dependencies |
| AI Integration | OpenAI API / local LLM via Ollama | Configurable provider for entity extraction and analysis |

### 14.3 Build and Development

| Tool | Purpose |
|------|---------|
| Vite | Build tooling and dev server |
| ESLint + Prettier | Code quality and formatting |
| Vitest | Unit and integration testing |
| Playwright | End-to-end testing |
| Docker | Optional containerized deployment |

---

## Appendix A: Entity Relationship Summary (Database)

This section summarizes the data relationships that drive the UI cross-referencing.

```
Documents ----< Events (source_document_id)
Documents ----< Communications (source_document_id)
Documents ----< MediaFiles (source_document_id)
Documents ----< FinancialTransactions (source_document_id)
Documents ----< EvidenceItems (source_document_id)

People ----< Relationships (person1_id, person2_id)
People ----< EventParticipants (person_id)
People ----< Communications (sender_person_id)
People ----< CommunicationRecipients (person_id)
People ----< FinancialTransactions (from_person_id, to_person_id)
People ----< MediaPeople (person_id)
People ----< VisualEntities (person_id)
People ----< Locations (owner_person_id)

Organizations ----< EventParticipants (organization_id)
Organizations ----< Communications (sender_organization_id)
Organizations ----< CommunicationRecipients (organization_id)
Organizations ----< FinancialTransactions (from_organization_id, to_organization_id)
Organizations ----< Locations (owner_organization_id)
Organizations ----< Organizations (parent_organization_id)

Locations ----< Events (location_id)
Locations ----< MediaFiles (location_id)
Locations ----< EvidenceItems (seized_from_location_id)

Events ----< EventParticipants
Events ----< MediaEvents

MediaFiles ----< ImageAnalysis
MediaFiles ----< VisualEntities
MediaFiles ----< MediaPeople
MediaFiles ----< MediaEvents
```

## Appendix B: Keyboard Shortcut Reference

| Shortcut | Context | Action |
|----------|---------|--------|
| `/` or `Ctrl+K` | Global | Focus search bar |
| `Escape` | Global | Close panel / modal / search |
| `1` through `9` | Global | Navigate to sidebar item by position |
| `P` | When entity selected | Pin / unpin entity |
| `B` | When entity selected | Add entity to board |
| `Enter` | List views | Open selected item |
| `Arrow Up/Down` | List views | Navigate list items |
| `Arrow Left/Right` | Timeline | Scroll timeline |
| `+` / `-` | Graph, Map, Timeline | Zoom in / out |
| `F` | Graph, Map | Fit all content in viewport |
| `Ctrl+E` | Any view | Export current view |
| `?` | Global | Show keyboard shortcut help |

## Appendix C: Glossary

| Term | Definition |
|------|-----------|
| EFTA Number | Unique identifier for each document in the dataset (format: EFTA followed by 8 digits) |
| Context Panel | The right-side slide-out panel showing entity details without full page navigation |
| Investigation Board | A user-created canvas for organizing findings, equivalent to a physical cork board |
| Entity | Any first-class data object: person, organization, event, document, location, communication, transaction, media file, or evidence item |
| Confidence Level | An assessment of data reliability: High, Medium, Low, or Unverified |
| Cross-Reference | The ability to navigate from any entity to all related entities of any type |
| Linked Brushing | Selecting a data range in one visualization and having other views filter to match |
| Ego-centric Graph | A network graph centered on a single node showing its direct connections |

---

*End of Product Requirements Document*
