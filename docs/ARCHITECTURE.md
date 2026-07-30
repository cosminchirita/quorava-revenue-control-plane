# Architecture

## Objective

Quorava demonstrates how a regulated finance or revenue-operations team can create a trustworthy reporting layer from heterogeneous operational inputs without hiding data-quality uncertainty.

## System context

The demo is intentionally local-first. Excel, JSON and SQLite sources are synthetic. The pipeline writes an immutable-style JSON snapshot, a queryable SQLite analytical model and a Power BI-ready CSV. A standard-library HTTP server exposes narrowly scoped read endpoints and serves the browser application.

## Pipeline stages

1. **Ingest** — source adapters emit raw rows with a source type, source reference and row number.
2. **Normalize** — aliases map to a canonical contract; dates, statuses, currency and monetary precision are standardized.
3. **Validate** — six versioned rules emit explicit issues. Source values are never silently repaired.
4. **Resolve identity** — a stable fingerprint groups the same order, date and normalized value. The winner is selected by issue count, trusted-source priority and source reference.
5. **Score anomalies** — median absolute deviation, discount thresholds, margin thresholds and quality confidence produce evidence-backed risk scores.
6. **Materialize** — facts, findings and a governed aggregation view are written to SQLite; the same snapshot feeds the API and Power BI export.
7. **Audit** — each material action appends an event whose hash includes the previous event hash.

## Production evolution

The repository is a functional demonstration, not a production topology. A production implementation would replace local connectors and storage with private network integrations, object storage, a managed warehouse, a durable orchestrator, workload identity, a secrets manager, centralized authorization, immutable audit retention, observability and disaster-recovery controls.

## Reliability properties

- deterministic demo clock, rules, exchange rates and source ordering;
- idempotent fingerprints and stable record identifiers;
- explicit data-contract and model versions on every snapshot;
- read-only SQL source access;
- generated outputs reconcile to the canonical in-memory result;
- the full pipeline can be re-run and verified with one command.

