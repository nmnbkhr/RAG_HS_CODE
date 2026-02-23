# Phase 1: Security & Validation - Requirements Document

**Phase:** 1 of 5
**Focus:** Security, Input Validation, Calculation Verification
**Status:** In Progress

---

## 1. OBJECTIVES

### Primary Goals
1. **Input Security** - Validate all user inputs to prevent errors and injection
2. **Calculation Accuracy** - Mathematically verify all duty calculations
3. **RAG Quality** - Ensure responses have proper citations and references
4. **API Security** - Protect sensitive credentials
5. **Error Handling** - Graceful error handling with user-friendly messages

---

## 2. DETAILED REQUIREMENTS

### 2.1 HS Code Validation

**Requirement ID:** P1-REQ-001
**Priority:** CRITICAL

#### Specification
```python
# Valid HS Code Formats:
# - 8 digits: XXXX.XXXX (e.g., 0808.1000)
# - 6 digits: XXXX.XX (e.g., 0808.10) -> normalize to 0808.1000
# - 4 digits: XXXX (e.g., 0808) -> normalize to 0808.0000
# - Chapter: XX (e.g., 08) -> search mode only

# Validation Rules:
# 1. First 2 digits (Chapter): 01-99
# 2. Digits 3-4 (Heading): 00-99
# 3. Digits 5-6 (Subheading): 00-99
# 4. Digits 7-8 (Tariff line): 00-99
```

#### Test Cases
| Input | Expected Output | Validation |
|-------|-----------------|------------|
| "0808.1000" | "0808.1000" | Valid |
| "0808.10" | "0808.1000" | Normalize |
| "0808" | "0808.0000" | Normalize |
| "08" | Search Chapter 08 | Valid for search |
| "abc" | Error: Invalid format | Reject |
| "0000.0000" | Error: Invalid chapter | Reject |
| "9999.9999" | "9999.9999" | Valid (may not exist) |
| "" | Error: Empty input | Reject |
| "0808.100000" | "0808.1000" | Truncate |

---

### 2.2 Calculation Validation

**Requirement ID:** P1-REQ-002
**Priority:** CRITICAL

#### Duty Calculation Formula
```
1. FOB Value = Unit Price × Quantity
2. CIF Value = FOB + Freight + Insurance + Other Charges
3. CIF (PKR) = CIF (Foreign) × Exchange Rate

4. Customs Duty (CD) = CIF (PKR) × CD Rate%
5. Additional Duty (AD) = CIF (PKR) × AD Rate%
6. Regulatory Duty (RD) = CIF (PKR) × RD Rate%

7. Sales Tax Base = CIF (PKR) + CD + AD + RD
8. Sales Tax (ST) = Sales Tax Base × ST Rate%

9. Income Tax (IT) = CIF (PKR) × IT Rate%

10. Total Duties = CD + AD + RD + ST + IT
11. Landed Cost = CIF (PKR) + Total Duties
```

#### Validation Test Cases
| Scenario | Input | Expected | Tolerance |
|----------|-------|----------|-----------|
| Basic Import | CIF=$1000, CD=20%, ST=18%, IT=5.5%, Rate=280 | CD=56,000, ST=12,600, IT=15,400 | ±0.01 |
| Zero Duty | CIF=$1000, CD=0%, ST=18%, IT=5.5%, Rate=280 | CD=0, ST=50,400, IT=15,400 | ±0.01 |
| With RD | CIF=$1000, CD=20%, RD=10%, ST=18%, Rate=280 | RD=28,000 | ±0.01 |
| Export | FOB=$1000, Rate=278 (TT Buy) | PKR=278,000 | ±0.01 |

---

### 2.3 RAG Response Validation

**Requirement ID:** P1-REQ-003
**Priority:** CRITICAL

#### Response Format Requirements
```
Every RAG response MUST include:
1. HS Code (8-digit format)
2. Description (from PCT)
3. Customs Duty percentage
4. Source reference (page number from PDF)
5. Confidence indicator (if available)
```

#### Expected Response Format
```
HS/PCT Code: 0808.1000
Description: Fresh apples
Customs Duty (CD): 20%
Source: Pakistan Customs Tariff FY 2024-25, Page 142
```

#### Validation Rules
- Response MUST contain HS code in XXXX.XXXX format
- Response MUST contain numeric duty rate
- Response SHOULD contain page reference
- Response MUST NOT hallucinate data not in PDF

---

### 2.4 Exchange Rate Validation

**Requirement ID:** P1-REQ-004
**Priority:** HIGH

#### Validation Rules
```python
# Valid PKR/USD rate range (as of 2024-2026)
MIN_RATE = 200.0
MAX_RATE = 400.0

# TT Buying < TT Selling (spread ~1-3 PKR)
# Imports use TT Selling (higher rate)
# Exports use TT Buying (lower rate)
```

#### Test Cases
| Source | Rate | Valid | Action |
|--------|------|-------|--------|
| NBP | 280.50 | Yes | Use |
| NBP | 150.00 | No | Reject, use fallback |
| NBP | 500.00 | No | Reject, use fallback |
| Timeout | N/A | No | Use cached/fallback |

---

### 2.5 API Security

**Requirement ID:** P1-REQ-005
**Priority:** HIGH

#### Requirements
1. API keys MUST NOT be in source code
2. API keys MUST be loaded from environment variables
3. .env file MUST be in .gitignore
4. API key validation on startup
5. Graceful handling of invalid/expired keys

---

### 2.6 Rate Limiting

**Requirement ID:** P1-REQ-006
**Priority:** HIGH

#### Limits
| Service | Max Requests | Period | Action on Exceed |
|---------|--------------|--------|------------------|
| WEBOC | 10 | 1 minute | Wait + Retry |
| NBP | 5 | 1 minute | Use cached |
| OpenAI | Per account limit | N/A | Error message |

---

### 2.7 Error Handling

**Requirement ID:** P1-REQ-007
**Priority:** HIGH

#### Error Categories
| Category | User Message | Log Level |
|----------|--------------|-----------|
| Validation Error | "Invalid HS code format. Use XXXX.XXXX" | WARNING |
| Network Error | "Service temporarily unavailable" | ERROR |
| API Error | "Unable to fetch data. Using cached rates." | WARNING |
| System Error | "An error occurred. Please try again." | CRITICAL |

---

## 3. IMPLEMENTATION CHECKLIST

### Files to Create
- [ ] `validators.py` - All validation functions
- [ ] `calculators.py` - Verified calculation functions
- [ ] `rate_limiter.py` - Rate limiting utility
- [ ] `logger.py` - Logging configuration
- [ ] `config.py` - Configuration management

### Tests to Create
- [ ] `test_validators.py` - HS code validation tests
- [ ] `test_calculators.py` - Calculation accuracy tests
- [ ] `test_rag_responses.py` - RAG output validation
- [ ] `test_exchange_rates.py` - Rate validation tests
- [ ] `test_error_handling.py` - Error scenario tests

---

## 4. ACCEPTANCE CRITERIA

| Criteria | Target | Measurement |
|----------|--------|-------------|
| HS Code Validation | 100% accuracy | Test suite |
| Calculation Accuracy | ±0.01 PKR | Test cases |
| RAG Citation Rate | 95%+ with page refs | Manual review |
| Error Handling | Zero unhandled exceptions | Crash reports |
| Test Coverage | 90%+ | pytest-cov |

---

## 5. DELIVERABLES

1. `validators.py` - Input validation module
2. `calculators.py` - Verified calculations
3. `test_*.py` - Test files
4. `AUDIT_REPORT.md` - Phase completion audit
5. Updated `appuiux.py` with validations integrated

---

*Document Version: 1.0*
*Created: 2026-01-25*
