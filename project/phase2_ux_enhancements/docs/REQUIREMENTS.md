# Phase 2: UX Enhancements - Requirements Document

**Phase:** 2 of 5
**Focus:** User Experience, Export, History, Smooth UI
**Status:** In Progress
**Depends On:** Phase 1 (Validators & Calculators)

---

## 1. OBJECTIVES

### Primary Goals
1. **Calculation History** - Track and display past calculations in session
2. **PDF Export** - Generate professional PDF reports of calculations
3. **Excel Export** - Export calculations with formulas to Excel
4. **Smooth UI** - No jumping, flickering, or jarring transitions
5. **Loading States** - Clear feedback during async operations

---

## 2. DETAILED REQUIREMENTS

### 2.1 Calculation History

**Requirement ID:** P2-REQ-001
**Priority:** HIGH

#### Specification
```python
# History Entry Structure
{
    "id": "uuid",
    "timestamp": "ISO datetime",
    "type": "import" | "export",
    "hs_code": "0808.1000",
    "description": "Fresh apples",
    "input_summary": {
        "quantity": 100,
        "unit": "kg",
        "value": 1000,
        "currency": "USD"
    },
    "result_summary": {
        "cif_pkr": 280000,
        "total_duties": 131880,
        "landed_cost": 411880
    },
    "full_result": {...}  # Complete CalculationResult
}
```

#### Features
- Store last 50 calculations in session
- Display history in sidebar or modal
- Click to restore calculation inputs
- Export history to CSV
- Clear history option

---

### 2.2 PDF Export

**Requirement ID:** P2-REQ-002
**Priority:** HIGH

#### PDF Structure
```
┌─────────────────────────────────────────────────┐
│            PAKISTAN CUSTOMS                      │
│        Duty Calculation Report                   │
├─────────────────────────────────────────────────┤
│ Date: 2026-01-25                                │
│ HS Code: 0808.1000                              │
│ Description: Fresh apples                        │
├─────────────────────────────────────────────────┤
│ INPUT VALUES                                     │
│ ─────────────                                    │
│ Quantity: 100 kg                                │
│ Unit Value: $10.00                              │
│ FOB Value: $1,000.00                            │
│ Exchange Rate: 280.00 PKR/USD                   │
├─────────────────────────────────────────────────┤
│ CIF BREAKDOWN                                    │
│ ─────────────                                    │
│ FOB Value (PKR):       280,000.00               │
│ Freight:                     0.00               │
│ Insurance:                   0.00               │
│ CIF Total:             280,000.00               │
├─────────────────────────────────────────────────┤
│ DUTY CALCULATION                                 │
│ ────────────────                                 │
│ Customs Duty (20%):     56,000.00               │
│ Sales Tax (18%):        60,480.00               │
│ Income Tax (5.5%):      15,400.00               │
│ ─────────────────────────────────               │
│ Total Duties:          131,880.00               │
├─────────────────────────────────────────────────┤
│ TOTAL LANDED COST:     411,880.00 PKR           │
├─────────────────────────────────────────────────┤
│ Data Sources:                                    │
│ - Exchange Rate: NBP TT Selling                 │
│ - Duty Rates: WEBOC / PCT Database              │
└─────────────────────────────────────────────────┘
```

---

### 2.3 Excel Export

**Requirement ID:** P2-REQ-003
**Priority:** HIGH

#### Excel Structure
- Sheet 1: Summary with key metrics
- Sheet 2: Detailed breakdown with formulas
- Formulas linked so user can modify values
- Professional formatting with borders

---

### 2.4 Smooth UI Transitions

**Requirement ID:** P2-REQ-004
**Priority:** CRITICAL

#### Requirements
- No page jumping when results appear
- Smooth loading animations
- Fixed-height containers where needed
- Progressive disclosure of information
- CSS transitions for state changes

#### Anti-Patterns to Avoid
- ❌ Content jumping when tabs load
- ❌ Buttons moving when clicked
- ❌ Spinner in wrong position
- ❌ Flash of unstyled content

---

### 2.5 Loading States

**Requirement ID:** P2-REQ-005
**Priority:** HIGH

#### Loading Indicators
| Action | Indicator | Location |
|--------|-----------|----------|
| Fetching WEBOC | Spinner + text | Button area |
| Calculating | Progress bar | Results area |
| Generating PDF | Download icon pulse | Button |
| Loading history | Skeleton cards | Sidebar |

---

## 3. IMPLEMENTATION CHECKLIST

### Files to Create
- [ ] `history_manager.py` - Session history management
- [ ] `pdf_exporter.py` - PDF report generation
- [ ] `excel_exporter.py` - Excel export with formulas
- [ ] `ui_components.py` - Reusable UI components

### Files to Modify
- [ ] `appuiux.py` - Integrate new features

### Tests to Create
- [ ] `test_history.py` - History management tests
- [ ] `test_pdf_export.py` - PDF generation tests
- [ ] `test_excel_export.py` - Excel export tests

---

## 4. ACCEPTANCE CRITERIA

| Criteria | Target | Measurement |
|----------|--------|-------------|
| History Persistence | 50 entries | Session test |
| PDF Generation | < 2 seconds | Performance |
| Excel Formulas | Working | Manual verify |
| UI Smoothness | No jumps | Visual test |
| Loading Feedback | All actions | Checklist |

---

## 5. DEPENDENCIES

### Python Packages
```
reportlab>=4.0.0      # PDF generation
openpyxl>=3.1.0       # Excel with formulas
```

---

*Document Version: 1.0*
*Created: 2026-01-25*
