"""
RAG_HS_CODE - Excel Export Module
Phase 2: UX Enhancements

Generates Excel workbooks with formulas for duty calculations using openpyxl.
"""

import io
from datetime import datetime
from typing import Dict, Any, Optional

from openpyxl import Workbook
from openpyxl.styles import (
    Font, Fill, PatternFill, Border, Side, Alignment, NamedStyle
)
from openpyxl.utils import get_column_letter


class DutyCalculationExcel:
    """
    Generates Excel workbooks for import/export duty calculations.

    Features:
    - Professional formatting
    - Working formulas (user can modify values)
    - Multiple sheets (Summary + Details)
    """

    # Colors
    HEADER_FILL = PatternFill(start_color="1e3a8a", end_color="1e3a8a", fill_type="solid")
    SECTION_FILL = PatternFill(start_color="f3f4f6", end_color="f3f4f6", fill_type="solid")
    TOTAL_FILL = PatternFill(start_color="dbeafe", end_color="dbeafe", fill_type="solid")

    # Fonts
    HEADER_FONT = Font(name='Calibri', size=12, bold=True, color="FFFFFF")
    TITLE_FONT = Font(name='Calibri', size=14, bold=True, color="1e3a8a")
    BOLD_FONT = Font(name='Calibri', size=11, bold=True)
    NORMAL_FONT = Font(name='Calibri', size=11)

    # Borders
    THIN_BORDER = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )

    def __init__(self):
        """Initialize Excel generator"""
        self.wb = None

    def generate_import_workbook(
        self,
        hs_code: str,
        description: str,
        quantity: float,
        unit: str,
        unit_value: float,
        currency: str,
        exchange_rate: float,
        exchange_rate_source: str,
        freight: float = 0,
        insurance: float = 0,
        other_charges: float = 0,
        customs_duty_rate: float = 0,
        additional_duty_rate: float = 0,
        regulatory_duty_rate: float = 0,
        federal_excise_duty_rate: float = 0,
        sales_tax_rate: float = 0,
        income_tax_rate: float = 0,
        data_source: str = "WEBOC"
    ) -> bytes:
        """
        Generate Excel workbook for import duty calculation with formulas.

        Returns:
            Excel file as bytes
        """
        self.wb = Workbook()

        # Remove default sheet and create new ones
        self.wb.remove(self.wb.active)

        # Create Summary sheet
        self._create_import_summary_sheet(
            hs_code, description, quantity, unit, unit_value, currency,
            exchange_rate, exchange_rate_source, freight, insurance,
            other_charges, customs_duty_rate, additional_duty_rate,
            regulatory_duty_rate, federal_excise_duty_rate,
            sales_tax_rate, income_tax_rate, data_source
        )

        # Create Calculation sheet with formulas
        self._create_import_calculation_sheet(
            quantity, unit_value, currency, exchange_rate,
            freight, insurance, other_charges,
            customs_duty_rate, additional_duty_rate,
            regulatory_duty_rate, federal_excise_duty_rate,
            sales_tax_rate, income_tax_rate
        )

        # Save to bytes
        buffer = io.BytesIO()
        self.wb.save(buffer)
        buffer.seek(0)
        return buffer.getvalue()

    def _create_import_summary_sheet(
        self,
        hs_code: str,
        description: str,
        quantity: float,
        unit: str,
        unit_value: float,
        currency: str,
        exchange_rate: float,
        exchange_rate_source: str,
        freight: float,
        insurance: float,
        other_charges: float,
        customs_duty_rate: float,
        additional_duty_rate: float,
        regulatory_duty_rate: float,
        federal_excise_duty_rate: float,
        sales_tax_rate: float,
        income_tax_rate: float,
        data_source: str
    ):
        """Create summary sheet"""
        ws = self.wb.create_sheet("Summary")

        # Set column widths
        ws.column_dimensions['A'].width = 25
        ws.column_dimensions['B'].width = 20
        ws.column_dimensions['C'].width = 15

        # Title
        ws.merge_cells('A1:C1')
        ws['A1'] = "PAKISTAN CUSTOMS - IMPORT DUTY CALCULATION"
        ws['A1'].font = self.TITLE_FONT
        ws['A1'].alignment = Alignment(horizontal='center')

        # Date
        ws['A2'] = f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        ws['A2'].font = Font(italic=True, size=9)

        row = 4

        # Item Details Section
        ws[f'A{row}'] = "ITEM DETAILS"
        ws[f'A{row}'].font = self.BOLD_FONT
        ws[f'A{row}'].fill = self.SECTION_FILL
        ws.merge_cells(f'A{row}:C{row}')
        row += 1

        details = [
            ("HS Code:", hs_code),
            ("Description:", description),
            ("Quantity:", f"{quantity:,.2f} {unit}"),
            ("Unit Value:", f"{unit_value:,.2f} {currency}"),
        ]

        for label, value in details:
            ws[f'A{row}'] = label
            ws[f'A{row}'].font = self.BOLD_FONT
            ws[f'B{row}'] = value
            row += 1

        row += 1

        # Exchange Rate Section
        ws[f'A{row}'] = "EXCHANGE RATE"
        ws[f'A{row}'].font = self.BOLD_FONT
        ws[f'A{row}'].fill = self.SECTION_FILL
        ws.merge_cells(f'A{row}:C{row}')
        row += 1

        ws[f'A{row}'] = "Rate:"
        ws[f'A{row}'].font = self.BOLD_FONT
        ws[f'B{row}'] = f"{exchange_rate:,.4f} PKR/{currency}"
        row += 1
        ws[f'A{row}'] = "Source:"
        ws[f'A{row}'].font = self.BOLD_FONT
        ws[f'B{row}'] = exchange_rate_source
        row += 2

        # Duty Rates Section
        ws[f'A{row}'] = "DUTY RATES"
        ws[f'A{row}'].font = self.BOLD_FONT
        ws[f'A{row}'].fill = self.SECTION_FILL
        ws.merge_cells(f'A{row}:C{row}')
        row += 1

        rates = [
            ("Customs Duty:", f"{customs_duty_rate}%"),
            ("Additional Duty:", f"{additional_duty_rate}%"),
            ("Regulatory Duty:", f"{regulatory_duty_rate}%"),
            ("Federal Excise Duty:", f"{federal_excise_duty_rate}%"),
            ("Sales Tax:", f"{sales_tax_rate}%"),
            ("Income Tax:", f"{income_tax_rate}%"),
        ]

        for label, value in rates:
            ws[f'A{row}'] = label
            ws[f'A{row}'].font = self.BOLD_FONT
            ws[f'B{row}'] = value
            row += 1

        row += 1

        # Data Source
        ws[f'A{row}'] = f"Data Source: {data_source}"
        ws[f'A{row}'].font = Font(italic=True, size=9)

        # Apply borders
        for r in range(1, row + 1):
            for c in range(1, 4):
                ws.cell(row=r, column=c).border = self.THIN_BORDER

    def _create_import_calculation_sheet(
        self,
        quantity: float,
        unit_value: float,
        currency: str,
        exchange_rate: float,
        freight: float,
        insurance: float,
        other_charges: float,
        customs_duty_rate: float,
        additional_duty_rate: float,
        regulatory_duty_rate: float,
        federal_excise_duty_rate: float,
        sales_tax_rate: float,
        income_tax_rate: float
    ):
        """Create calculation sheet with working formulas"""
        ws = self.wb.create_sheet("Calculation")

        # Set column widths
        ws.column_dimensions['A'].width = 30
        ws.column_dimensions['B'].width = 20
        ws.column_dimensions['C'].width = 25
        ws.column_dimensions['D'].width = 15

        # Title
        ws.merge_cells('A1:D1')
        ws['A1'] = "DUTY CALCULATION WITH FORMULAS"
        ws['A1'].font = self.TITLE_FONT
        ws['A1'].alignment = Alignment(horizontal='center')

        ws['A2'] = "Modify yellow cells to recalculate"
        ws['A2'].font = Font(italic=True, size=9, color="666666")

        row = 4

        # Input Section Header
        ws[f'A{row}'] = "INPUT VALUES"
        ws[f'A{row}'].font = self.HEADER_FONT
        ws[f'A{row}'].fill = self.HEADER_FILL
        ws[f'B{row}'] = "Value"
        ws[f'B{row}'].font = self.HEADER_FONT
        ws[f'B{row}'].fill = self.HEADER_FILL
        ws[f'C{row}'] = "Notes"
        ws[f'C{row}'].font = self.HEADER_FONT
        ws[f'C{row}'].fill = self.HEADER_FILL
        row += 1

        # Editable inputs (yellow background)
        input_fill = PatternFill(start_color="fffbeb", end_color="fffbeb", fill_type="solid")

        inputs = [
            ("Quantity", quantity, "units", "B5"),
            ("Unit Value", unit_value, currency, "B6"),
            ("Exchange Rate", exchange_rate, f"PKR/{currency}", "B7"),
            ("Freight", freight, currency, "B8"),
            ("Insurance", insurance, currency, "B9"),
            ("Other Charges", other_charges, currency, "B10"),
        ]

        input_cells = {}
        for label, value, note, cell_ref in inputs:
            ws[f'A{row}'] = label
            ws[f'A{row}'].font = self.BOLD_FONT
            ws[f'B{row}'] = value
            ws[f'B{row}'].fill = input_fill
            ws[f'B{row}'].number_format = '#,##0.00'
            ws[f'C{row}'] = note
            input_cells[label] = f'B{row}'
            row += 1

        row += 1

        # Duty Rates Section
        ws[f'A{row}'] = "DUTY RATES (%)"
        ws[f'A{row}'].font = self.HEADER_FONT
        ws[f'A{row}'].fill = self.HEADER_FILL
        ws.merge_cells(f'A{row}:C{row}')
        row += 1

        rate_inputs = [
            ("Customs Duty Rate", customs_duty_rate, "B12"),
            ("Additional Duty Rate", additional_duty_rate, "B13"),
            ("Regulatory Duty Rate", regulatory_duty_rate, "B14"),
            ("Federal Excise Duty Rate", federal_excise_duty_rate, "B15"),
            ("Sales Tax Rate", sales_tax_rate, "B16"),
            ("Income Tax Rate", income_tax_rate, "B17"),
        ]

        rate_cells = {}
        for label, value, cell_ref in rate_inputs:
            ws[f'A{row}'] = label
            ws[f'A{row}'].font = self.BOLD_FONT
            ws[f'B{row}'] = value
            ws[f'B{row}'].fill = input_fill
            ws[f'B{row}'].number_format = '0.00'
            ws[f'C{row}'] = "%"
            rate_cells[label] = f'B{row}'
            row += 1

        row += 1

        # Calculations Section
        ws[f'A{row}'] = "CALCULATED VALUES"
        ws[f'A{row}'].font = self.HEADER_FONT
        ws[f'A{row}'].fill = self.HEADER_FILL
        ws[f'B{row}'] = "PKR"
        ws[f'B{row}'].font = self.HEADER_FONT
        ws[f'B{row}'].fill = self.HEADER_FILL
        ws[f'C{row}'] = "Formula"
        ws[f'C{row}'].font = self.HEADER_FONT
        ws[f'C{row}'].fill = self.HEADER_FILL
        row += 1

        # FOB Value (Foreign)
        ws[f'A{row}'] = "FOB Value (Foreign)"
        ws[f'B{row}'] = f"=B5*B6"  # Quantity * Unit Value
        ws[f'B{row}'].number_format = '#,##0.00'
        ws[f'C{row}'] = "Quantity × Unit Value"
        fob_foreign_row = row
        row += 1

        # CIF Value (Foreign)
        ws[f'A{row}'] = "CIF Value (Foreign)"
        ws[f'B{row}'] = f"=B{fob_foreign_row}+B8+B9+B10"  # FOB + Freight + Insurance + Other
        ws[f'B{row}'].number_format = '#,##0.00'
        ws[f'C{row}'] = "FOB + Freight + Insurance + Other"
        cif_foreign_row = row
        row += 1

        # CIF Value (PKR)
        ws[f'A{row}'] = "CIF Value (PKR)"
        ws[f'B{row}'] = f"=B{cif_foreign_row}*B7"  # CIF Foreign × Exchange Rate
        ws[f'B{row}'].number_format = '#,##0.00'
        ws[f'B{row}'].fill = self.TOTAL_FILL
        ws[f'C{row}'] = "CIF Foreign × Exchange Rate"
        cif_pkr_row = row
        row += 1

        row += 1

        # Duties — use rate_cells for dynamic references
        cd_rate_cell = rate_cells["Customs Duty Rate"]
        ad_rate_cell = rate_cells["Additional Duty Rate"]
        rd_rate_cell = rate_cells["Regulatory Duty Rate"]
        fed_rate_cell = rate_cells["Federal Excise Duty Rate"]
        st_rate_cell = rate_cells["Sales Tax Rate"]
        it_rate_cell = rate_cells["Income Tax Rate"]

        ws[f'A{row}'] = "Customs Duty"
        ws[f'B{row}'] = f"=B{cif_pkr_row}*{cd_rate_cell}/100"
        ws[f'B{row}'].number_format = '#,##0.00'
        ws[f'C{row}'] = "CIF × CD%"
        cd_row = row
        row += 1

        ws[f'A{row}'] = "Additional Duty"
        ws[f'B{row}'] = f"=B{cif_pkr_row}*{ad_rate_cell}/100"
        ws[f'B{row}'].number_format = '#,##0.00'
        ws[f'C{row}'] = "CIF × AD%"
        ad_row = row
        row += 1

        ws[f'A{row}'] = "Regulatory Duty"
        ws[f'B{row}'] = f"=B{cif_pkr_row}*{rd_rate_cell}/100"
        ws[f'B{row}'].number_format = '#,##0.00'
        ws[f'C{row}'] = "CIF × RD%"
        rd_row = row
        row += 1

        ws[f'A{row}'] = "Federal Excise Duty"
        ws[f'B{row}'] = f"=(B{cif_pkr_row}+B{cd_row})*{fed_rate_cell}/100"
        ws[f'B{row}'].number_format = '#,##0.00'
        ws[f'C{row}'] = "(CIF + CD) × FED%"
        fed_row = row
        row += 1

        # Sales Tax Base
        ws[f'A{row}'] = "Sales Tax Base"
        ws[f'B{row}'] = f"=B{cif_pkr_row}+B{cd_row}+B{ad_row}+B{rd_row}+B{fed_row}"
        ws[f'B{row}'].number_format = '#,##0.00'
        ws[f'C{row}'] = "CIF + CD + AD + RD + FED"
        st_base_row = row
        row += 1

        ws[f'A{row}'] = "Sales Tax"
        ws[f'B{row}'] = f"=B{st_base_row}*{st_rate_cell}/100"
        ws[f'B{row}'].number_format = '#,##0.00'
        ws[f'C{row}'] = "ST Base × ST%"
        st_row = row
        row += 1

        ws[f'A{row}'] = "Income Tax"
        ws[f'B{row}'] = f"=B{cif_pkr_row}*{it_rate_cell}/100"
        ws[f'B{row}'].number_format = '#,##0.00'
        ws[f'C{row}'] = "CIF × IT%"
        it_row = row
        row += 1

        row += 1

        # Totals
        ws[f'A{row}'] = "TOTAL DUTIES"
        ws[f'A{row}'].font = self.BOLD_FONT
        ws[f'B{row}'] = f"=B{cd_row}+B{ad_row}+B{rd_row}+B{fed_row}+B{st_row}+B{it_row}"
        ws[f'B{row}'].number_format = '#,##0.00'
        ws[f'B{row}'].font = self.BOLD_FONT
        ws[f'B{row}'].fill = self.TOTAL_FILL
        ws[f'C{row}'] = "CD + AD + RD + FED + ST + IT"
        total_duties_row = row
        row += 1

        ws[f'A{row}'] = "TOTAL LANDED COST"
        ws[f'A{row}'].font = Font(name='Calibri', size=12, bold=True, color="FFFFFF")
        ws[f'A{row}'].fill = self.HEADER_FILL
        ws[f'B{row}'] = f"=B{cif_pkr_row}+B{total_duties_row}"
        ws[f'B{row}'].number_format = '#,##0.00'
        ws[f'B{row}'].font = Font(name='Calibri', size=12, bold=True, color="FFFFFF")
        ws[f'B{row}'].fill = self.HEADER_FILL
        ws[f'C{row}'] = "CIF + Total Duties"
        ws[f'C{row}'].font = Font(name='Calibri', size=11, color="FFFFFF")
        ws[f'C{row}'].fill = self.HEADER_FILL

        # Apply borders
        for r in range(1, row + 1):
            for c in range(1, 4):
                ws.cell(row=r, column=c).border = self.THIN_BORDER

    def generate_export_workbook(
        self,
        hs_code: str,
        description: str,
        quantity: float,
        unit: str,
        fob_per_unit: float,
        currency: str,
        exchange_rate: float,
        exchange_rate_source: str,
        regulatory_duty_rate: float = 0,
        export_scheme: str = "Normal Export",
        destination: str = ""
    ) -> bytes:
        """
        Generate Excel workbook for export proceeds calculation.

        Returns:
            Excel file as bytes
        """
        self.wb = Workbook()

        # Remove default sheet and create new one
        self.wb.remove(self.wb.active)
        ws = self.wb.create_sheet("Export Calculation")

        # Set column widths
        ws.column_dimensions['A'].width = 30
        ws.column_dimensions['B'].width = 20
        ws.column_dimensions['C'].width = 25

        # Title
        ws.merge_cells('A1:C1')
        ws['A1'] = "PAKISTAN CUSTOMS - EXPORT PROCEEDS CALCULATION"
        ws['A1'].font = self.TITLE_FONT
        ws['A1'].alignment = Alignment(horizontal='center')

        ws['A2'] = f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        ws['A2'].font = Font(italic=True, size=9)

        row = 4

        # Item Details
        ws[f'A{row}'] = "ITEM DETAILS"
        ws[f'A{row}'].font = self.HEADER_FONT
        ws[f'A{row}'].fill = self.HEADER_FILL
        ws.merge_cells(f'A{row}:C{row}')
        row += 1

        details = [
            ("HS Code:", hs_code),
            ("Description:", description),
            ("Destination:", destination or "Not specified"),
            ("Export Scheme:", export_scheme),
        ]

        for label, value in details:
            ws[f'A{row}'] = label
            ws[f'A{row}'].font = self.BOLD_FONT
            ws[f'B{row}'] = value
            row += 1

        row += 1

        # Input Section
        input_fill = PatternFill(start_color="fffbeb", end_color="fffbeb", fill_type="solid")

        ws[f'A{row}'] = "INPUT VALUES (Editable)"
        ws[f'A{row}'].font = self.HEADER_FONT
        ws[f'A{row}'].fill = self.HEADER_FILL
        ws.merge_cells(f'A{row}:C{row}')
        row += 1

        ws[f'A{row}'] = "Quantity"
        ws[f'B{row}'] = quantity
        ws[f'B{row}'].fill = input_fill
        ws[f'B{row}'].number_format = '#,##0.00'
        ws[f'C{row}'] = unit
        qty_row = row
        row += 1

        ws[f'A{row}'] = "FOB per Unit"
        ws[f'B{row}'] = fob_per_unit
        ws[f'B{row}'].fill = input_fill
        ws[f'B{row}'].number_format = '#,##0.00'
        ws[f'C{row}'] = currency
        fob_unit_row = row
        row += 1

        ws[f'A{row}'] = "Exchange Rate (TT Buying)"
        ws[f'B{row}'] = exchange_rate
        ws[f'B{row}'].fill = input_fill
        ws[f'B{row}'].number_format = '#,##0.0000'
        ws[f'C{row}'] = f"PKR/{currency}"
        rate_row = row
        row += 1

        ws[f'A{row}'] = "Regulatory Duty Rate"
        ws[f'B{row}'] = regulatory_duty_rate
        ws[f'B{row}'].fill = input_fill
        ws[f'B{row}'].number_format = '0.00'
        ws[f'C{row}'] = "%"
        rd_rate_row = row
        row += 2

        # Calculations
        ws[f'A{row}'] = "CALCULATIONS"
        ws[f'A{row}'].font = self.HEADER_FONT
        ws[f'A{row}'].fill = self.HEADER_FILL
        ws.merge_cells(f'A{row}:C{row}')
        row += 1

        ws[f'A{row}'] = "Total FOB (Foreign)"
        ws[f'B{row}'] = f"=B{qty_row}*B{fob_unit_row}"
        ws[f'B{row}'].number_format = '#,##0.00'
        ws[f'C{row}'] = f"Qty × FOB/unit"
        fob_total_row = row
        row += 1

        ws[f'A{row}'] = "Total FOB (PKR)"
        ws[f'B{row}'] = f"=B{fob_total_row}*B{rate_row}"
        ws[f'B{row}'].number_format = '#,##0.00'
        ws[f'B{row}'].fill = self.TOTAL_FILL
        ws[f'C{row}'] = "FOB × Exchange Rate"
        fob_pkr_row = row
        row += 1

        ws[f'A{row}'] = "Regulatory Duty"
        ws[f'B{row}'] = f"=B{fob_pkr_row}*B{rd_rate_row}/100"
        ws[f'B{row}'].number_format = '#,##0.00'
        ws[f'C{row}'] = "FOB PKR × RD%"
        rd_amount_row = row
        row += 2

        # Net Proceeds
        ws[f'A{row}'] = "NET EXPORT PROCEEDS"
        ws[f'A{row}'].font = Font(name='Calibri', size=12, bold=True, color="FFFFFF")
        ws[f'A{row}'].fill = self.HEADER_FILL
        ws[f'B{row}'] = f"=B{fob_pkr_row}-B{rd_amount_row}"
        ws[f'B{row}'].number_format = '#,##0.00'
        ws[f'B{row}'].font = Font(name='Calibri', size=12, bold=True, color="FFFFFF")
        ws[f'B{row}'].fill = self.HEADER_FILL
        ws[f'C{row}'] = "FOB PKR - RD"
        ws[f'C{row}'].font = Font(name='Calibri', size=11, color="FFFFFF")
        ws[f'C{row}'].fill = self.HEADER_FILL

        # Apply borders
        for r in range(1, row + 1):
            for c in range(1, 4):
                ws.cell(row=r, column=c).border = self.THIN_BORDER

        # Save to bytes
        buffer = io.BytesIO()
        self.wb.save(buffer)
        buffer.seek(0)
        return buffer.getvalue()


def generate_import_excel(calculation_result: Dict[str, Any]) -> bytes:
    """
    Convenience function to generate import Excel from calculation result.

    Args:
        calculation_result: Dictionary from ImportDutyCalculator

    Returns:
        Excel file as bytes
    """
    excel = DutyCalculationExcel()
    return excel.generate_import_workbook(
        hs_code=calculation_result.get('hs_code', 'N/A'),
        description=calculation_result.get('description', 'Import calculation'),
        quantity=calculation_result.get('quantity', 0),
        unit=calculation_result.get('unit_of_measure', 'units'),
        unit_value=calculation_result.get('unit_value_foreign', 0),
        currency=calculation_result.get('currency', 'USD'),
        exchange_rate=calculation_result.get('exchange_rate', 280),
        exchange_rate_source=calculation_result.get('exchange_rate_source', 'NBP'),
        freight=calculation_result.get('freight_foreign', 0),
        insurance=calculation_result.get('insurance_foreign', 0),
        other_charges=calculation_result.get('other_charges_foreign', 0),
        customs_duty_rate=calculation_result.get('customs_duty_rate', 0),
        additional_duty_rate=calculation_result.get('additional_duty_rate', 0),
        regulatory_duty_rate=calculation_result.get('regulatory_duty_rate', 0),
        federal_excise_duty_rate=calculation_result.get('federal_excise_duty_rate', 0),
        sales_tax_rate=calculation_result.get('sales_tax_rate', 0),
        income_tax_rate=calculation_result.get('income_tax_rate', 0),
        data_source=calculation_result.get('data_source', 'WEBOC')
    )


if __name__ == "__main__":
    # Quick test
    print("Testing Excel Export...")

    excel = DutyCalculationExcel()

    # Test import Excel
    import_excel = excel.generate_import_workbook(
        hs_code="0808.1000",
        description="Fresh apples",
        quantity=100,
        unit="kg",
        unit_value=10.0,
        currency="USD",
        exchange_rate=280.0,
        exchange_rate_source="NBP TT Selling",
        freight=0,
        insurance=0,
        other_charges=0,
        customs_duty_rate=20.0,
        additional_duty_rate=0,
        regulatory_duty_rate=0,
        sales_tax_rate=18.0,
        income_tax_rate=5.5
    )

    # Save test Excel
    with open('/tmp/test_import.xlsx', 'wb') as f:
        f.write(import_excel)

    print(f"  ✓ Import Excel generated: {len(import_excel)} bytes")
    print("  ✓ Saved to /tmp/test_import.xlsx")
