# Decisions and Resolved Ambiguities (DECISIONS.md)

This document outlines the resolved ambiguities, assumptions made, questions for the Product Manager (PM), and the scope of data shapes handled in this prototype.

---

## 1. Ambiguities Resolved & Selected Approaches

### 1.1 Mock Authentication & Tenant Switcher
- **Ambiguity**: How should users and tenants be managed?
- **Decision**: Instead of building a complex login/JWT screen, we implemented a custom header-based session switcher (`X-Mock-User` header).
- **Rationale**: This allows a reviewer or evaluator to toggle between different accounts (e.g. `acme_analyst` vs `eco_analyst` or `acme_auditor`) with a single click. The backend intercepts this header, resolves it to the correct `UserProfile` and `Tenant`, and enforces strict database query isolation. This prioritizes proving data isolation and role permissions over building boilerplate auth UI.

### 1.2 Serving React from Django (Single Service Deployment)
- **Ambiguity**: How should the frontend and backend be deployed?
- **Decision**: Compile React into static assets via Vite, copy them to `/frontend/dist`, and let Django serve them via Whitenoise.
- **Rationale**: ESG startups often need fast prototypes with minimal infrastructure overhead. Serving both from a single cloud instance (on Render/Railway) avoids cross-origin resource sharing (CORS) security configuration pitfalls, reduces latency, and runs on a single free/cheap service tier.

### 1.3 Missing Travel Segment Distances
- **Ambiguity**: Travel CSVs often list origin/destination airports but lack flight distance.
- **Decision**: Pre-seeded a global database of standard airport coordinates (IATA codes). The backend dynamically calculates the Great Circle Distance using the mathematical Haversine formula and categorizes flights.
- **Rationale**: Relying on mock distances is not audit-grade. Implementing the actual Haversine distance matches real-world carbon accounting pipelines (e.g., using airport lookups).

### 1.4 Calendar-Month Proration of Utility Bills
- **Ambiguity**: Utility cycles do not align with calendar months, but corporate carbon accounting requires monthly proration.
- **Decision**: Store the raw utility bill as a single normalized record (preserving 1-to-1 traceability to the raw upload) but compute proration on-the-fly inside the `/api/normalized-records/dashboard-stats/` endpoint. If a bill covers $N$ days and overlaps a month by $D$ days, we allocate $D/N$ of the usage and emissions to that month's chart column.
- **Rationale**: Keeps the ledger clean and traceable, while still giving the sustainability lead accurate calendar-month timelines.

---

## 2. Ingestion Scope: Handled vs. Ignored

### 2.1 SAP Fuel & Procurement
- **Handled**: Standard CSV exports of Goods Movements (e.g., transaction code `MB51` or table `MSEG`). Includes German field headers/abbreviations (`MBLNR`, `WERKS`, `BUDAT`, `MATNR`, `MENGE`, `MEINS`). German decimals (e.g., `1.250,50`) are parsed and corrected.
- **Ignored**: Direct SAP integration via BAPIs, OData Gateway Services, or IDocs. Real-world SAP systems require complex network configurations (VPN, RFC) which are out of scope for a prototype.
- **Filtering**: Unrelated material document rows (e.g., procurement of steel rebars or office supplies) are automatically parsed, categorized as non-emissions, marked as `SKIPPED`, and omitted from emissions calculations, keeping the review grid clean.

### 2.2 Utility Electricity
- **Handled**: Utility portal CSV exports (e.g., National Grid, PG&E) detailing account IDs, meter numbers, usage in kWh, and billing dates.
- **Ignored**: PDF scraping/OCR. Scrapers are highly brittle and fail whenever a utility provider adjusts their bill layout.
- **Overlap check**: If an uploaded utility row overlaps with an existing, non-rejected billing period for the same meter number, the row is parsed but flagged as `SUSPICIOUS` with a warning badge.

### 2.3 Corporate Travel
- **Handled**: CSV segments representing Flights (calculating Haversine distance, short/long-haul boundaries, and cabin multipliers), Hotels (nights, country-specific EF lookup), and Car Rentals (vehicle categories, distance).
- **Ignored**: Expense receipt PDFs, train travel, and complex multi-leg multi-passenger allocations.
- **Estimations**: If car rental distance is missing but rental days are present, we estimate distance as 80 km/day and flag the row as `SUSPICIOUS` for analyst confirmation.

---

## 3. Product Manager (PM) Questions

If this were a live project, we would ask the PM:
1. **Auditor Unlock Flow**: "Once an analyst signs off and approves a record, it becomes read-only (locked). If an auditor requests a correction, what should the unlock/re-review flow look like? Should admins have override rights, and what additional audit logs must be generated?"
2. **Retroactive Factor Updates**: "If a regulatory body (e.g., DEFRA or EPA) updates an emission factor retroactively, should we recalculate historical approved records, or should they remain locked to preserve historical audit states?"
3. **Multi-Currency & Cost Integration**: "Utility and travel data contain cost fields. Should we normalize currencies (e.g., EUR to USD) and build cost-vs-carbon dashboard KPIs to help client companies evaluate procurement efficiency?"
