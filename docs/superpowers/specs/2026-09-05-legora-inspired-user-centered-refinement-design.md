# LexSync user-centered interface refinement

Date: 2026-09-05

## Objective

Refine the existing LexSync frontend using the principles in `docs/research/legora-uiux-deep-dive.md`. The result must serve two audiences without creating separate products:

- Legal and compliance operators who review changes, inspect sources, and act on affected documents daily.
- Senior stakeholders who need a rapid, trustworthy view of exposure, urgency, and decisions.

The solution uses progressive disclosure: each screen begins with a concise decision layer, continues into the operational workspace, and ends with evidence and provenance where relevant.

## Product principles

1. **Answer before detail.** Users should understand the state and next action before reading tables or legal text.
2. **Editorial outside, operational inside.** Page framing may use expressive typography and generous space; work surfaces remain compact and precise.
3. **One dominant action.** Each screen has at most one filled primary action.
4. **Evidence stays close.** Source, date, impact rationale, and affected assets remain accessible within one interaction.
5. **Calm is hierarchy, not omission.** Reduce visual competition without hiding compliance-critical information.
6. **Responsive composition.** Small screens switch between list and detail states rather than compressing desktop columns.

## Visual system

### Typography

- Use a licensed/open editorial serif for display and page-title moments only, with a fallback serif stack that remains usable before a webfont loads.
- Continue using Geist for navigation, controls, tables, metadata, labels, and legal content.
- Display: `clamp(2.75rem, 5vw, 5.5rem)`, line-height 0.98.
- Page title: `clamp(2rem, 3vw, 2.75rem)`, line-height 1.05.
- Body: 14–16px, line-height 1.55–1.7.
- Metadata: 12–13px; eyebrows: 11px with moderate letter spacing.

### Spacing and geometry

- Formalize 4, 8, 12, 16, 24, 32, 48, 64, and 96px spacing stops.
- Use 64–96px around major page ideas, 32–48px between related regions, and 8–24px inside components.
- Page gutters use `clamp(20px, 4vw, 64px)`.
- Reading text is constrained to 680–760px.
- Product surfaces use 8–12px radii and quiet translucent borders; default shadows are removed.

### Color and selection

- Warm canvas, near-white work surfaces, near-black ink, and restrained sage accent.
- Red, amber, and green remain semantic.
- Navigation and row selection use a soft tonal fill plus a subtle edge/marker, not a dark filled block.
- Blue legacy styles are removed from the active system.

### Motion

- Editorial entry motion may use 400–700ms opacity/translation.
- Product state changes use 120–200ms transitions.
- No animated legal-text reflow or critical alerts.
- `prefers-reduced-motion` disables nonessential animation.

## Shared shell

- Desktop sidebar is 224px, with 40px navigation rows and a quiet selected state.
- The top utility bar remains 56–64px and provides current context; page titles move into page content.
- The content area supports both spacious overview pages and edge-efficient operational workspaces.
- Below 1024px the sidebar becomes a drawer or compact rail. Below 768px it becomes a menu-controlled overlay.
- Navigation state remains owned by `App`; backend contracts do not change.

## Dashboard journey

### User question

“What changed, what matters, and what should I inspect next?”

### Hierarchy

1. Eyebrow identifying the MAS regulatory workspace.
2. Editorial title and a one-sentence explanation.
3. A compact attention statement derived from available document/impact counts.
4. Three summary metrics in a simple divided row.
5. Feed controls with one primary action: Fetch new.
6. Master-detail regulatory workspace.

The list and detail panel remain available without additional navigation. The list receives a tinted surface and calmer selection. The detail pane receives a readable document measure, clearer metadata grouping, and source access near the title.

Loading, empty, stale-data error, and no-selection states state what happened and what the user can do next.

## Regulatory Changes journey

### User question

“Which changes create exposure, and which internal documents require action?”

### Hierarchy

1. Page title, explanation, and concise count/impact statement.
2. One filter surface with type, topic, category, and date ordering.
3. A readable results table optimized for scanning title, date, impact, and affected count.
4. Selecting a change opens the existing affected-document workflow.

Rows use 44–48px minimum height, faint horizontal rules, quiet hover, and a visible keyboard focus state. Long titles may wrap. Mobile replaces the six-column table with stacked result rows or cards showing only decision-critical fields; selecting one opens detail as a separate state.

## Impact Map journey

### Current state

The feature has no data-backed graph yet. This refinement must not imply that it does.

### Empty-state hierarchy

1. Page-level explanation of the value of relationship mapping.
2. A purposeful empty work surface showing what will connect: regulation → affected policy → required action.
3. A clear prerequisite and next action directing users to ingest or review documents where the current product supports it.

The decorative grid is reduced. Future graph controls and provenance-drawer geometry may be prepared structurally, but no unsupported interaction is introduced.

## Resilience Analysis journey

### User question

“Does this regulatory text conflict with our document, why, and what wording should change?”

### Input state

- Introduce a clear page title and four-step progress indicator: Inputs, Analyse, Findings, Decision.
- Place both inputs in one shared comparison workspace divided into Regulation and Internal asset.
- Preserve paste and file-upload behavior. Make file precedence explicit next to each input.
- Keep one primary action: Run analysis.

### Loading and error states

- During analysis, lock duplicate submission and describe the active task.
- Errors remain adjacent to the action and identify whether the user can retry.

### Results state

1. Decision statement summarizing affected clauses.
2. Four metrics in a quiet divided row.
3. Prioritized finding summary.
4. Per-asset cards containing redline, legal reasoning, citations, similarity, and analysis source.

Affected status is semantic and prominent; similarity and provenance remain secondary. Zero matches produce a meaningful explanation and next-step guidance.

## Component boundaries

- `PageIntro`: eyebrow, display/page title, description, optional status summary.
- `MetricStrip`: shared divided metric row; replaces visually inconsistent metric treatments.
- `WorkspacePanel`: shared quiet surface for operational regions.
- Existing `Button`, `Badge`, document list, detail, and analysis components are refined in place where their responsibilities remain clear.
- View components retain screen-specific data preparation. Shared visual components do not own business logic.

Avoid introducing a broad design-system abstraction for every primitive. Extract only components used across multiple views or needed to enforce key hierarchy.

## Data flow and behavior

- The existing `useDocuments` hook remains the shared regulatory-document source.
- Existing fetching, refreshing, filtering, sorting, selection, analysis submission, affected-document navigation, and external-source behavior remain intact.
- Visual summaries derive from current frontend data and existing impact helpers.
- No backend endpoint, payload, persistence rule, or mock-impact calculation changes in this work.

## Accessibility

- All actions remain native buttons or links.
- Table rows that behave as navigation must provide an equivalent focusable control.
- Focus visibility must work on all interactive elements.
- Semantic information cannot rely on color alone.
- Layout must remain usable at 200% browser zoom.
- Touch targets are at least 40px where practical.
- Reduced-motion preferences are respected.

## Testing strategy

Use test-driven development for behavior-visible structural changes:

- Shared page hierarchy renders expected labels and actions.
- Dashboard retains fetching, refreshing, document selection, loading, empty, and error behavior.
- Regulatory filters, sorting, row/detail navigation, and empty results remain functional.
- Analysis inputs, file precedence messaging, submission, loading, errors, no-match state, and results hierarchy remain functional.
- Impact Map states an honest prerequisite and does not expose fake graph controls.
- Sidebar navigation remains accessible and current-page semantics remain correct.

Run component tests, the complete frontend test suite, and a production build. Visual QA should cover 1440px, 1024px, 768px, and 390px widths when a browser-rendering surface is available.

## Out of scope

- Backend changes.
- A functional impact graph.
- New ingestion workflows not already supported by the application.
- Legora proprietary fonts, imagery, marks, or copied page compositions.
- Authentication, user roles, persistence, notifications, or executive exports.

## Acceptance criteria

- Each view answers its primary user question before exposing detailed controls or data.
- Both senior and operator workflows are supported without a separate mode toggle.
- Each screen has no more than one dominant filled action.
- Dense legal content remains readable and provenance stays within one interaction.
- The visual system consistently distinguishes macro page spacing from compact operational spacing.
- Existing behavior and backend contracts are preserved.
- Layout composition works across desktop, tablet, and mobile breakpoints.
- Automated frontend tests and production build pass.

