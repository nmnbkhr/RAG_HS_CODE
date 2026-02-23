"""
RAG_HS_CODE - Batch Processing Module
Phase 4: Features

Process multiple import duty calculations from CSV/Excel input.
Integrates with Phase 1 calculators for verified calculations.
"""

import csv
import io
import json
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum


class RowStatus(Enum):
    """Status of a processed row"""
    SUCCESS = "success"
    VALIDATION_ERROR = "validation_error"
    CALCULATION_ERROR = "calculation_error"
    SKIPPED = "skipped"


@dataclass
class BatchRow:
    """A single row in a batch with its processing result"""
    row_number: int
    hs_code: str
    description: str
    quantity: float
    unit: str
    unit_value: float
    currency: str
    freight: float = 0.0
    insurance: float = 0.0
    other_charges: float = 0.0

    # Rates (can be provided or fetched)
    customs_duty_rate: Optional[float] = None
    sales_tax_rate: Optional[float] = None
    income_tax_rate: Optional[float] = None
    additional_duty_rate: Optional[float] = None
    regulatory_duty_rate: Optional[float] = None
    federal_excise_duty_rate: Optional[float] = None

    # Processing results
    status: RowStatus = RowStatus.SKIPPED
    error_message: str = ""

    # Calculated values (populated after processing)
    exchange_rate: float = 0.0
    exchange_rate_source: str = ""
    cif_value_foreign: float = 0.0
    cif_value_pkr: float = 0.0
    customs_duty_amount: float = 0.0
    additional_duty_amount: float = 0.0
    regulatory_duty_amount: float = 0.0
    federal_excise_duty_amount: float = 0.0
    sales_tax_amount: float = 0.0
    income_tax_amount: float = 0.0
    total_duties: float = 0.0
    total_landed_cost: float = 0.0
    effective_duty_rate: float = 0.0


@dataclass
class BatchResult:
    """Complete result of a batch processing run"""
    batch_id: str
    timestamp: str
    total_rows: int
    processed: int
    succeeded: int
    failed: int
    skipped: int
    rows: List[BatchRow] = field(default_factory=list)
    exchange_rate: float = 0.0
    exchange_rate_source: str = ""
    processing_time_ms: float = 0.0

    @property
    def success_rate(self) -> float:
        if self.total_rows == 0:
            return 0.0
        return round(self.succeeded / self.total_rows * 100, 1)

    @property
    def total_landed_cost_all(self) -> float:
        return sum(r.total_landed_cost for r in self.rows if r.status == RowStatus.SUCCESS)

    @property
    def total_duties_all(self) -> float:
        return sum(r.total_duties for r in self.rows if r.status == RowStatus.SUCCESS)

    def get_errors(self) -> List[Dict[str, Any]]:
        return [
            {"row": r.row_number, "hs_code": r.hs_code, "error": r.error_message}
            for r in self.rows
            if r.status in (RowStatus.VALIDATION_ERROR, RowStatus.CALCULATION_ERROR)
        ]

    def to_summary_dict(self) -> Dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "timestamp": self.timestamp,
            "total_rows": self.total_rows,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "skipped": self.skipped,
            "success_rate": self.success_rate,
            "total_duties": round(self.total_duties_all, 2),
            "total_landed_cost": round(self.total_landed_cost_all, 2),
            "exchange_rate": self.exchange_rate,
            "processing_time_ms": self.processing_time_ms,
            "errors": self.get_errors()
        }


# Column name mapping (handles common variations)
COLUMN_ALIASES = {
    "hs_code": ["hs_code", "hscode", "hs code", "pct_code", "pctcode", "tariff_code", "code"],
    "description": ["description", "desc", "item", "item_description", "product", "goods"],
    "quantity": ["quantity", "qty", "units", "amount"],
    "unit": ["unit", "uom", "unit_of_measure", "measure"],
    "unit_value": ["unit_value", "value", "price", "unit_price", "price_per_unit", "fob_value"],
    "currency": ["currency", "curr", "ccy"],
    "freight": ["freight", "frt"],
    "insurance": ["insurance", "ins"],
    "other_charges": ["other_charges", "other", "misc"],
    "customs_duty_rate": ["customs_duty", "cd_rate", "cd", "customs_duty_rate"],
    "sales_tax_rate": ["sales_tax", "st_rate", "st", "sales_tax_rate", "gst"],
    "income_tax_rate": ["income_tax", "it_rate", "it", "income_tax_rate", "wht"],
    "additional_duty_rate": ["additional_duty", "ad_rate", "ad", "additional_duty_rate"],
    "regulatory_duty_rate": ["regulatory_duty", "rd_rate", "rd", "regulatory_duty_rate"],
    "federal_excise_duty_rate": ["federal_excise_duty", "fed_rate", "fed", "federal_excise_duty_rate", "excise"],
}


def _resolve_column(header: str) -> Optional[str]:
    """Resolve a header name to a standard column name."""
    normalized = header.strip().lower().replace(" ", "_")
    for standard_name, aliases in COLUMN_ALIASES.items():
        if normalized in aliases:
            return standard_name
    return None


def parse_csv(csv_content: str) -> Tuple[List[Dict[str, str]], List[str]]:
    """
    Parse CSV content into rows.

    Args:
        csv_content: Raw CSV string content

    Returns:
        Tuple of (list of row dicts, list of errors)
    """
    errors = []
    rows = []

    try:
        reader = csv.DictReader(io.StringIO(csv_content))
        if not reader.fieldnames:
            return [], ["CSV file has no headers"]

        # Map headers to standard names
        column_map = {}
        for header in reader.fieldnames:
            resolved = _resolve_column(header)
            if resolved:
                column_map[header] = resolved

        if "hs_code" not in column_map.values():
            return [], ["Required column 'hs_code' not found. Found columns: " +
                       ", ".join(reader.fieldnames)]

        for i, raw_row in enumerate(reader, start=2):  # Row 1 is header
            mapped = {}
            for original_col, standard_col in column_map.items():
                val = raw_row.get(original_col, "").strip()
                if val:
                    mapped[standard_col] = val
            mapped["_row_number"] = i
            rows.append(mapped)

    except csv.Error as e:
        errors.append(f"CSV parsing error: {str(e)}")

    return rows, errors


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert a value to float."""
    if value is None or value == "":
        return default
    try:
        cleaned = str(value).replace(",", "").strip()
        return float(cleaned)
    except (ValueError, TypeError):
        return default


def validate_row(row: Dict[str, str], row_number: int) -> Tuple[Optional[BatchRow], str]:
    """
    Validate a single row and create a BatchRow.

    Args:
        row: Dictionary of column values
        row_number: Row number for error reporting

    Returns:
        Tuple of (BatchRow or None, error_message)
    """
    hs_code = row.get("hs_code", "").strip()
    if not hs_code:
        return None, "HS code is required"

    # Validate HS code format (basic check)
    import re
    digits = re.sub(r'\D', '', hs_code)
    if len(digits) < 4:
        return None, f"Invalid HS code: '{hs_code}' (minimum 4 digits)"

    # Validate quantity
    quantity = _safe_float(row.get("quantity"), 0.0)
    if quantity <= 0:
        return None, f"Quantity must be positive, got: {row.get('quantity', 'empty')}"

    # Validate unit value
    unit_value = _safe_float(row.get("unit_value"), 0.0)
    if unit_value <= 0:
        return None, f"Unit value must be positive, got: {row.get('unit_value', 'empty')}"

    # Currency
    currency = row.get("currency", "USD").strip().upper()
    if len(currency) != 3:
        return None, f"Invalid currency code: '{currency}'"

    # Optional fields
    unit = row.get("unit", "kg").strip() or "kg"
    description = row.get("description", "").strip() or f"Item {hs_code}"
    freight = _safe_float(row.get("freight"), 0.0)
    insurance = _safe_float(row.get("insurance"), 0.0)
    other_charges = _safe_float(row.get("other_charges"), 0.0)

    if freight < 0 or insurance < 0 or other_charges < 0:
        return None, "Freight, insurance, and other charges cannot be negative"

    # Duty rates (optional - can be fetched later)
    cd_rate = _safe_float(row.get("customs_duty_rate"), None)
    st_rate = _safe_float(row.get("sales_tax_rate"), None)
    it_rate = _safe_float(row.get("income_tax_rate"), None)
    ad_rate = _safe_float(row.get("additional_duty_rate"), None)
    rd_rate = _safe_float(row.get("regulatory_duty_rate"), None)
    fed_rate = _safe_float(row.get("federal_excise_duty_rate"), None)

    return BatchRow(
        row_number=row_number,
        hs_code=hs_code,
        description=description,
        quantity=quantity,
        unit=unit,
        unit_value=unit_value,
        currency=currency,
        freight=freight,
        insurance=insurance,
        other_charges=other_charges,
        customs_duty_rate=cd_rate if cd_rate != 0.0 or row.get("customs_duty_rate") else None,
        sales_tax_rate=st_rate if st_rate != 0.0 or row.get("sales_tax_rate") else None,
        income_tax_rate=it_rate if it_rate != 0.0 or row.get("income_tax_rate") else None,
        additional_duty_rate=ad_rate if ad_rate != 0.0 or row.get("additional_duty_rate") else None,
        regulatory_duty_rate=rd_rate if rd_rate != 0.0 or row.get("regulatory_duty_rate") else None,
        federal_excise_duty_rate=fed_rate if fed_rate != 0.0 or row.get("federal_excise_duty_rate") else None,
    ), ""


def calculate_row(
    row: BatchRow,
    exchange_rate: float,
    exchange_rate_source: str,
    default_rates: Optional[Dict[str, float]] = None
) -> BatchRow:
    """
    Calculate duties for a single validated row.

    Args:
        row: Validated BatchRow
        exchange_rate: PKR exchange rate
        exchange_rate_source: Rate source description
        default_rates: Default duty rates if not provided per-row

    Returns:
        BatchRow with calculated values filled in
    """
    try:
        defaults = default_rates or {}

        cd_rate = row.customs_duty_rate if row.customs_duty_rate is not None else defaults.get("customs_duty", 0.0)
        st_rate = row.sales_tax_rate if row.sales_tax_rate is not None else defaults.get("sales_tax", 18.0)
        it_rate = row.income_tax_rate if row.income_tax_rate is not None else defaults.get("income_tax", 5.5)
        ad_rate = row.additional_duty_rate if row.additional_duty_rate is not None else defaults.get("additional_duty", 0.0)
        rd_rate = row.regulatory_duty_rate if row.regulatory_duty_rate is not None else defaults.get("regulatory_duty", 0.0)
        fed_rate = row.federal_excise_duty_rate if row.federal_excise_duty_rate is not None else defaults.get("federal_excise_duty", 0.0)

        # FOB value
        fob_value = row.quantity * row.unit_value

        # CIF foreign
        cif_foreign = fob_value + row.freight + row.insurance + row.other_charges

        # CIF PKR
        cif_pkr = cif_foreign * exchange_rate

        # Duties
        customs_duty = cif_pkr * (cd_rate / 100)
        additional_duty = cif_pkr * (ad_rate / 100)
        regulatory_duty = cif_pkr * (rd_rate / 100)
        federal_excise_duty = (cif_pkr + customs_duty) * (fed_rate / 100)
        st_base = cif_pkr + customs_duty + additional_duty + regulatory_duty + federal_excise_duty
        sales_tax = st_base * (st_rate / 100)
        income_tax = cif_pkr * (it_rate / 100)

        total_duties = customs_duty + additional_duty + regulatory_duty + federal_excise_duty + sales_tax + income_tax
        landed_cost = cif_pkr + total_duties
        effective_rate = (total_duties / cif_pkr * 100) if cif_pkr > 0 else 0.0

        # Update row
        row.exchange_rate = exchange_rate
        row.exchange_rate_source = exchange_rate_source
        row.cif_value_foreign = round(cif_foreign, 2)
        row.cif_value_pkr = round(cif_pkr, 2)
        row.customs_duty_rate = cd_rate
        row.sales_tax_rate = st_rate
        row.income_tax_rate = it_rate
        row.additional_duty_rate = ad_rate
        row.regulatory_duty_rate = rd_rate
        row.federal_excise_duty_rate = fed_rate
        row.customs_duty_amount = round(customs_duty, 2)
        row.additional_duty_amount = round(additional_duty, 2)
        row.regulatory_duty_amount = round(regulatory_duty, 2)
        row.federal_excise_duty_amount = round(federal_excise_duty, 2)
        row.sales_tax_amount = round(sales_tax, 2)
        row.income_tax_amount = round(income_tax, 2)
        row.total_duties = round(total_duties, 2)
        row.total_landed_cost = round(landed_cost, 2)
        row.effective_duty_rate = round(effective_rate, 2)
        row.status = RowStatus.SUCCESS

    except Exception as e:
        row.status = RowStatus.CALCULATION_ERROR
        row.error_message = str(e)

    return row


def process_batch(
    csv_content: str,
    exchange_rate: float,
    exchange_rate_source: str = "NBP",
    default_rates: Optional[Dict[str, float]] = None,
    max_rows: int = 10000
) -> BatchResult:
    """
    Process a batch of import calculations from CSV content.

    Args:
        csv_content: Raw CSV string
        exchange_rate: PKR exchange rate to use
        exchange_rate_source: Rate source description
        default_rates: Default duty rates for rows without explicit rates
        max_rows: Maximum rows to process

    Returns:
        BatchResult with all processed rows
    """
    import time
    start_time = time.time()

    batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    timestamp = datetime.now().isoformat()

    # Parse CSV
    raw_rows, parse_errors = parse_csv(csv_content)

    if parse_errors:
        return BatchResult(
            batch_id=batch_id,
            timestamp=timestamp,
            total_rows=0,
            processed=0,
            succeeded=0,
            failed=len(parse_errors),
            skipped=0,
            rows=[],
            exchange_rate=exchange_rate,
            exchange_rate_source=exchange_rate_source
        )

    # Limit rows
    if len(raw_rows) > max_rows:
        raw_rows = raw_rows[:max_rows]

    succeeded = 0
    failed = 0
    processed_rows = []

    for raw_row in raw_rows:
        row_num = raw_row.get("_row_number", 0)

        # Validate
        batch_row, error = validate_row(raw_row, row_num)
        if batch_row is None:
            failed_row = BatchRow(
                row_number=row_num,
                hs_code=raw_row.get("hs_code", ""),
                description=raw_row.get("description", ""),
                quantity=0,
                unit="",
                unit_value=0,
                currency="",
                status=RowStatus.VALIDATION_ERROR,
                error_message=error
            )
            processed_rows.append(failed_row)
            failed += 1
            continue

        # Calculate
        batch_row = calculate_row(batch_row, exchange_rate, exchange_rate_source, default_rates)

        if batch_row.status == RowStatus.SUCCESS:
            succeeded += 1
        else:
            failed += 1

        processed_rows.append(batch_row)

    processing_time = (time.time() - start_time) * 1000

    return BatchResult(
        batch_id=batch_id,
        timestamp=timestamp,
        total_rows=len(raw_rows),
        processed=len(processed_rows),
        succeeded=succeeded,
        failed=failed,
        skipped=len(raw_rows) - len(processed_rows),
        rows=processed_rows,
        exchange_rate=exchange_rate,
        exchange_rate_source=exchange_rate_source,
        processing_time_ms=round(processing_time, 2)
    )


def export_batch_csv(result: BatchResult) -> str:
    """
    Export batch results to CSV string.

    Args:
        result: BatchResult to export

    Returns:
        CSV content as string
    """
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "Row", "Status", "HS Code", "Description", "Qty", "Unit",
        "Unit Value", "Currency", "Freight", "Insurance", "Other",
        "Exchange Rate", "CIF Foreign", "CIF PKR",
        "CD Rate%", "CD Amount", "AD Rate%", "AD Amount",
        "RD Rate%", "RD Amount", "FED Rate%", "FED Amount",
        "ST Rate%", "ST Amount",
        "IT Rate%", "IT Amount", "Total Duties", "Landed Cost",
        "Effective Rate%", "Error"
    ])

    for row in result.rows:
        writer.writerow([
            row.row_number,
            row.status.value,
            row.hs_code,
            row.description,
            row.quantity,
            row.unit,
            row.unit_value,
            row.currency,
            row.freight,
            row.insurance,
            row.other_charges,
            row.exchange_rate,
            row.cif_value_foreign,
            row.cif_value_pkr,
            row.customs_duty_rate or 0,
            row.customs_duty_amount,
            row.additional_duty_rate or 0,
            row.additional_duty_amount,
            row.regulatory_duty_rate or 0,
            row.regulatory_duty_amount,
            row.federal_excise_duty_rate or 0,
            row.federal_excise_duty_amount,
            row.sales_tax_rate or 0,
            row.sales_tax_amount,
            row.income_tax_rate or 0,
            row.income_tax_amount,
            row.total_duties,
            row.total_landed_cost,
            row.effective_duty_rate,
            row.error_message
        ])

    # Summary row
    writer.writerow([])
    writer.writerow(["SUMMARY"])
    writer.writerow(["Total Rows", result.total_rows])
    writer.writerow(["Succeeded", result.succeeded])
    writer.writerow(["Failed", result.failed])
    writer.writerow(["Total Duties", round(result.total_duties_all, 2)])
    writer.writerow(["Total Landed Cost", round(result.total_landed_cost_all, 2)])
    writer.writerow(["Exchange Rate", result.exchange_rate])
    writer.writerow(["Processing Time (ms)", result.processing_time_ms])

    return output.getvalue()


def generate_sample_csv() -> str:
    """Generate a sample CSV template for batch processing."""
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "hs_code", "description", "quantity", "unit", "unit_value",
        "currency", "freight", "insurance", "other_charges",
        "customs_duty", "sales_tax", "income_tax"
    ])

    # Sample rows
    samples = [
        ["0808.1000", "Fresh apples", 100, "kg", 10.0, "USD", 50, 10, 0, 20, 18, 5.5],
        ["8517.1200", "Mobile phones", 50, "units", 200.0, "USD", 100, 20, 0, 0, 18, 5.5],
        ["6109.1000", "Cotton T-shirts", 500, "units", 5.0, "USD", 80, 15, 0, 20, 18, 5.5],
        ["8703.2300", "Motor vehicles", 1, "units", 25000.0, "USD", 500, 250, 100, 50, 18, 6],
    ]

    for sample in samples:
        writer.writerow(sample)

    return output.getvalue()
