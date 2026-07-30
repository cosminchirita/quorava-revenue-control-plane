# Security and privacy

## Demo controls

- local-only network binding by default;
- restrictive content security policy and frame denial;
- no permissive cross-origin response headers;
- fixed read-only SQL query;
- HTTP connector allowlists `http` and `https`, requires JSON, enforces a timeout and caps payload size;
- API searches and identifiers are length-bounded;
- static file paths are resolved and checked against the web root;
- customer-facing labels are minimized;
- audit events keep hashes of payloads rather than duplicating full financial records;
- no runtime secrets are required.

## Threat model summary

The primary demo risks are malicious local input files, oversized API responses, path traversal, browser injection, unauthorized pipeline reruns and accidental use with real financial data. The included controls reduce those risks, but production deployment requires organizational authentication, role-based authorization, malware scanning, rate limiting, encrypted storage, key management, retention enforcement, centralized logging and tested incident response.

## Data classification

All bundled data is classified `SYNTHETIC / PUBLIC DEMO`. Do not replace it with real invoices, customer exports, credentials, bank data or personal data in a public fork.

