# Phase 4: Features - Requirements

## Overview
Power-user features: batch processing, duty comparison, favorites, multi-currency.

## Requirements

### P4-REQ-001: Batch Processing (CSV/Excel)
- Parse CSV and Excel files with multiple items
- Required columns: hs_code, quantity, unit_value, currency
- Optional columns: unit, freight, insurance, other_charges, description
- Run ImportDutyCalculator for each row
- Per-row validation with detailed error reporting
- Graceful handling: skip invalid rows, continue processing
- Generate consolidated CSV/Excel output with full breakdown
- Support 100+ items per batch
- Progress tracking for UI feedback

### P4-REQ-002: Duty Comparison Mode
- Compare up to 5 HS codes side-by-side
- Same input values (quantity, unit_value, exchange_rate) across all codes
- Show per-code duty breakdown (CD, ST, IT, AD, RD)
- Calculate total duties and landed cost per code
- Highlight best (lowest) and worst (highest) duty scenarios
- Effective duty rate comparison
- Ranked results by total cost

### P4-REQ-003: HS Code Favorites/Bookmarks
- Save HS codes with custom notes/tags
- Persistent SQLite storage
- Search and filter favorites
- Quick-recall for calculator pre-fill
- Import/export favorites as JSON
- Maximum 500 favorites

### P4-REQ-004: Multi-Currency Rate Manager
- Support all major currencies (USD, EUR, GBP, AED, SAR, CNY, JPY, etc.)
- Cross-rate calculation via PKR base
- Rate history (last N fetched rates per currency)
- Integration with Phase 3 ExchangeRateCache
- Currency code validation (ISO 4217)

## Acceptance Criteria
- Batch: Process 100+ items without failure
- Comparison: Compare up to 5 HS codes simultaneously
- Favorites: Save/load 500+ entries
- Currencies: Support 10+ currency pairs
- All calculations verified via Phase 1 calculators
- All tests passing
