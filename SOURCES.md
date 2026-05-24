# Ingestion Sources Research (SOURCES.md)

This document details the real-world research behind the three ESG data sources (SAP, Utility, Travel), explains the schema shapes of our mock data, and outlines what would break in a production deployment.

---

## 1. SAP Fuel & Procurement Ingestion

### Real-World Research
In SAP ERP environments, companies track material consumption and procurement under standard inventory tables:
- **MSEG** (Document Segment: Material): Logs every goods movement.
- **EKBE** (History per Purchase Order Document): Logs service and goods receipts.
Sustainability leads typically extract report exports using transaction **MB51** (Goods Movement list).
Standard SAP columns use strict German technical abbreviations:
- `MBLNR` (Materialbeleg): Material Document Number
- `BUDAT` (Buchungsdatum): Posting Date (often formatted as `YYYYMMDD` or `DD.MM.YYYY` depending on user locale)
- `WERKS` (Werk): Plant Code (e.g., `1000`, `DE01`)
- `MATNR` (Material): Material Number
- `MENGE` (Menge): Quantity (often containing German commas as decimal separators, e.g., `1.250,00`)
- `MEINS` (Einheit): Base Unit of Measure (e.g., `L`, `KG`, `TO`, `M3`)
- `MAKTX` (Materialkurztext): Description

### Sample Data Shape (`sap_mock.csv`)
```csv
MBLNR,BUDAT,WERKS,MATNR,MENGE,MEINS,MAKTX
DOC001,2026-04-10,US10,DIESEL,"1,500.00",L,Generator backup diesel
DOC002,2026-04-12,DE20,GASOLINE,"1.250,50",LTR,Fleet refueling
DOC003,2026-04-15,US10,STEEL-001,500.00,KG,Unrelated office steel rebars
DOC004,2026-04-20,US10,NATURAL_GAS,400.00,M3,Boiler gas combustion
```
- **Why this shape?**: Represents standard exports containing both emissions activity (fuels) and non-emissions data (Steel), testing the parser's ability to skip rows and clean European number formats.

### What would break in production
1. **Custom Material Numbers**: Large companies customize material IDs (e.g., standard diesel is mapped to `Z_DSL_COMMERCIAL_09`). A rigid parser looking only for `DIESEL` would fail.
2. **Plant Code Gaps**: Mergers and acquisitions introduce plants (e.g., `WERKS = "PL99"`) before the sustainability admin registers them in the facilities database, causing row rejections.
3. **Movement Types**: Not all material movements represent combustion. An inventory transfer between warehouses (Movement Type `301`) does not produce emissions, whereas consumption (Movement Type `201` or `261`) does. A real parser must filter by movement type codes (`BWART`).

---

## 2. Utility Electricity Ingestion

### Real-World Research
Utility companies (such as PG&E, National Grid, Consolidated Edison) allow corporate customers to download historical billing records or scrape them via Green Button XML/CSV.
A typical portal CSV export contains:
- `Account ID` / `Account Number`
- `Meter ID` / `Meter Number` (unique identifier)
- `Billing Start` / `Start Date`
- `Billing End` / `End Date`
- `Usage kWh` / `Active Energy Usage`
- `Demand kW` (Peak load)
- `Cost` / `Charges ($)`

### Sample Data Shape (`utility_mock.csv`)
```csv
Account Number,Meter Number,Start Date,End Date,Usage kWh
ACME-ELEC-99,METER-CA-101,2026-04-12,2026-05-11,15400
ACME-ELEC-88,METER-DE-202,2026-04-01,2026-04-30,8900
ACME-ELEC-99,METER-CA-101,2026-05-01,2026-05-15,6200
```
- **Why this shape?**: Tests calendar-month proration (April 12 to May 11 covers parts of two months) and billing cycle overlaps (the third row overlaps with the first row, triggering a `SUSPICIOUS` validation state).

### What would break in production
1. **Meter Replacements**: When a utility provider replaces a physical meter, the meter number changes, but the account remains the same. If the lookup database is not updated, uploads will fail with "Unknown Meter ID".
2. **Estimated Billing**: Utilities often issue bills based on estimated usage and correct them the following month. This creates back-dated adjustments that overlap previous billing periods, complicating the ledger.
3. **Reactive Power Tariffs**: Large industrial facilities pay charges for reactive power factor penalties (kVARh). The parser must ignore kVARh values and only extract active power (kWh) to calculate carbon.

---

## 3. Corporate Travel Ingestion

### Real-World Research
Travel management companies (TMCs) like SAP Concur, Navan (formerly TripActions), or Egencia expose travel itineraries via automated reports.
A standard segments CSV export contains:
- `Booking ID` / `Itinerary ID`
- `Transaction Date`
- `Type`: Flight, Hotel, Car Rental, Rail
- Flight details: Departure and Destination Airport IATA codes, Cabin Class (Economy, Business, First)
- Hotel details: Room Nights, Country (2-letter ISO), City, Rate
- Car details: Vehicle category (Compact, SUV, EV), Distance traveled, Fuel type

### Sample Data Shape (`travel_mock.csv`)
```csv
Booking ID,Date,Type,Flight Origin,Flight Destination,Cabin Class,Hotel Country,Hotel Nights,Car Category,Distance km,Rental Days
TKT-701,2026-04-15,Flight,SFO,JFK,Business,,,,,
TKT-702,2026-04-16,Hotel,,,,,GB,3,,,
TKT-703,2026-04-18,Car,,,,,,,Electric,120.0,
TKT-704,2026-04-19,Car,,,,,,,Gasoline,,4
```
- **Why this shape?**: Represents travel booking lines:
  - Flight from SFO to JFK in Business class (evaluates Haversine distance, long-haul classification, and $2.9\times$ business class carbon multiplier).
  - Hotel stay in the UK (looks up UK specific hotel EF).
  - Electric car rental with known distance.
  - Gasoline car rental with missing distance but known rental days (triggers distance estimation of $4 \times 80 = 320 \text{ km}$ and flags as `SUSPICIOUS`).

### What would break in production
1. **Multi-Leg Flight Itineraries**: A flight from San Francisco to London with a layover in New York (e.g. `SFO-JFK-LHR`) must be calculated as two separate segments to apply the correct distances and flight haul categories. If the file simply lists `SFO` and `LHR` as origin/destination, it under-reports emissions.
2. **Missing IATA Codes**: Regional airports in remote areas might not exist in a pre-seeded Airport table. A production system needs to hook into a live global aviation API (like OpenSky or IATA DB) to dynamically download coordinates.
3. **Hotel Room Sharing**: If two employees share a single hotel room, the expense platform might log two hotel night transactions. A naive ESG calculator would double-count the emissions, requiring deduplication algorithms.
