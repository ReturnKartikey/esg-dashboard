# Architectural Trade-Offs (TRADEOFFS.md)

This document details three capabilities we deliberately chose not to build for this prototype and the technical and product rationale behind these decisions.

---

## 1. Brittle PDF OCR Ingestion for Utility Bills

### What we did not build
An ingestion pipeline that accepts PDF utility bills, performs Optical Character Recognition (OCR), and extracts dates and meter quantities.

### Rationale
1. **Low Reliability & Brittle Pipelines**: PDF parsing using regex or standard OCR is notoriously fragile. If PG&E or National Grid updates their billing design (e.g. changing column positions or adding promotional banners), parser templates break instantly.
2. **Security & Financial Risk**: For audit-ready ESG reporting, data must be precise. OCR pipelines can misread decimals (e.g. reading `1020.50` as `102050`), introducing material errors that could lead to financial or regulatory penalties.
3. **High Run Costs**: Building an audit-grade PDF extractor requires integrating commercial cloud document extractors (like AWS Textract or Azure AI Document Intelligence) or LLM-based parsers. This introduces expensive external API call dependencies, third-party API key management, and latency.
4. **Alternative**: Facilities teams have access to utility web portals where they can export structured billing ledgers as CSVs. Handling structured CSV portal scrapes is far more secure, cost-effective, and audit-safe.

---

## 2. Live API Connectors (Concur / Navan OAuth Flows)

### What we did not build
A direct OAuth2 integration that connects to SAP Concur or Navan APIs to fetch travel segments in real-time.

### Rationale
1. **Credential & Sandbox Access**: Enterprise APIs require vendor developer accounts, client secrets, and dedicated sandboxes. These are impossible to provision for a prototype.
2. **Complexity vs. Value**: Building an OAuth2 handshake, webhooks, token refresh loops, and queue managers takes days of engineering time. It would displace our focus from carbon data normalizations and auditor review tools.
3. **Enterprise Reality**: In the real world, ESG onboarding often starts before API agreements are signed. Providing a structured CSV upload channel acts as the mandatory manual fallback that clients rely on for historical data ingestion.
4. **Alternative**: We designed our travel engine to parse CSV reports exported from Concur/Navan, matching the exact schemas the APIs expose, which can be easily migrated to API endpoints in a production phase.

---

## 3. Asynchronous Worker Queue (Celery & Redis)

### What we did not build
An asynchronous file parsing backend using Celery, Redis, or Django Channels.

### Rationale
1. **Operational Complexity**: Introducing Celery requires running a Redis broker, setting up worker daemons (supervisord/systemd), and managing database concurrency locks. This triples the deployment complexity and increases cloud resource requirements.
2. **Scale Suitability**: The prototype is designed to process monthly and quarterly files (typically containing 100 to 2,000 rows). Standard Python CSV parsing of 2,000 rows takes less than 1.5 seconds. Running this inside the HTTP request cycle is acceptable and safe from Gunicorn timeout limits.
3. **Alternative**: In production, if clients upload files with 100,000+ rows, we would migrate the `run_parser_on_csv` task to a background celery worker. For the prototype, synchronous parsing inside a database transaction simplifies deployment and provides instant feedback in the UI.
