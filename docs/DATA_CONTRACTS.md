# Data contracts and lineage

The canonical grain is one revenue event per resolved order, transaction date and normalized net amount.

## Canonical fields

Identifiers remain strings. Dates use ISO `YYYY-MM-DD`. Monetary source values retain their original currency, while analytical values are normalized to EUR using the versioned synthetic rate table. `source_ref`, `source_row` and `lineage_hash` make each event traceable.

## Quality behavior

Contract failures produce separate issues with rule ID, severity, field, explanation and observed value. They lower confidence but remain visible in the canonical output so a reviewer can inspect the evidence. The demo never changes a source amount to force reconciliation.

## Identity resolution

The demo fingerprint is derived from order ID, ISO transaction date and normalized net amount. Candidate precedence is deterministic: fewer quality issues first, then SQL, API and Excel. Removed candidates remain in the duplicate register.

## Exchange rates

`config/exchange_rates.json` contains fixed synthetic rates for reproducibility. These values are not current FX market data and must not be used for financial reporting.

