"""
RAG_HS_CODE - PDF Export Module
Phase 2: UX Enhancements

Generates professional PDF reports for duty calculations using ReportLab.
"""

import io
from datetime import datetime
from typing import Dict, Any, Optional
from dataclasses import dataclass

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, Image
)
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT


@dataclass
class PDFConfig:
    """Configuration for PDF generation"""
    page_size: tuple = A4
    margin_left: float = 1 * inch
    margin_right: float = 1 * inch
    margin_top: float = 0.75 * inch
    margin_bottom: float = 0.75 * inch
    title: str = "Pakistan Customs - Duty Calculation Report"
    include_footer: bool = True
    include_disclaimer: bool = True


class DutyCalculationPDF:
    """
    Generates PDF reports for import/export duty calculations.

    Usage:
        pdf = DutyCalculationPDF()
        pdf_bytes = pdf.generate_import_report(calculation_result)
    """

    # Colors
    HEADER_BG = colors.HexColor('#1e3a8a')  # Dark blue
    HEADER_TEXT = colors.white
    SECTION_BG = colors.HexColor('#f3f4f6')  # Light gray
    BORDER_COLOR = colors.HexColor('#d1d5db')
    ACCENT_COLOR = colors.HexColor('#3b82f6')  # Blue

    def __init__(self, config: PDFConfig = None):
        """Initialize with optional configuration"""
        self.config = config or PDFConfig()
        self._styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Setup custom paragraph styles"""
        self._styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self._styles['Title'],
            fontSize=18,
            textColor=self.HEADER_BG,
            spaceAfter=12
        ))

        self._styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self._styles['Heading2'],
            fontSize=12,
            textColor=self.HEADER_BG,
            spaceBefore=12,
            spaceAfter=6
        ))

        self._styles.add(ParagraphStyle(
            name='SmallText',
            parent=self._styles['Normal'],
            fontSize=8,
            textColor=colors.gray
        ))

        self._styles.add(ParagraphStyle(
            name='RightAligned',
            parent=self._styles['Normal'],
            alignment=TA_RIGHT
        ))

    def generate_import_report(
        self,
        hs_code: str,
        description: str,
        quantity: float,
        unit: str,
        unit_value: float,
        currency: str,
        exchange_rate: float,
        exchange_rate_source: str,
        fob_value: float,
        freight: float,
        insurance: float,
        other_charges: float,
        cif_foreign: float,
        cif_pkr: float,
        customs_duty_rate: float,
        customs_duty_amount: float,
        additional_duty_rate: float = 0,
        additional_duty_amount: float = 0,
        regulatory_duty_rate: float = 0,
        regulatory_duty_amount: float = 0,
        federal_excise_duty_rate: float = 0,
        federal_excise_duty_amount: float = 0,
        sales_tax_rate: float = 0,
        sales_tax_amount: float = 0,
        income_tax_rate: float = 0,
        income_tax_amount: float = 0,
        total_duties: float = 0,
        landed_cost: float = 0,
        data_source: str = "WEBOC"
    ) -> bytes:
        """
        Generate PDF for import duty calculation.

        Returns:
            PDF file as bytes
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=self.config.page_size,
            leftMargin=self.config.margin_left,
            rightMargin=self.config.margin_right,
            topMargin=self.config.margin_top,
            bottomMargin=self.config.margin_bottom
        )

        elements = []

        # Header
        elements.append(self._create_header("IMPORT DUTY CALCULATION"))
        elements.append(Spacer(1, 0.2 * inch))

        # Document info
        info_data = [
            ['Date:', datetime.now().strftime('%Y-%m-%d %H:%M')],
            ['HS Code:', hs_code],
            ['Description:', description[:50] + '...' if len(description) > 50 else description],
        ]
        info_table = Table(info_data, colWidths=[1.5 * inch, 4 * inch])
        info_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(info_table)
        elements.append(Spacer(1, 0.3 * inch))

        # Input Values Section
        elements.append(Paragraph("INPUT VALUES", self._styles['SectionHeader']))
        input_data = [
            ['Quantity:', f"{quantity:,.2f} {unit}"],
            ['Unit Value:', f"{unit_value:,.2f} {currency}"],
            ['FOB Value:', f"{fob_value:,.2f} {currency}"],
            ['Exchange Rate:', f"{exchange_rate:,.4f} PKR/{currency}"],
            ['Rate Source:', exchange_rate_source],
        ]
        elements.append(self._create_data_table(input_data))
        elements.append(Spacer(1, 0.2 * inch))

        # CIF Breakdown Section
        elements.append(Paragraph("CIF BREAKDOWN", self._styles['SectionHeader']))
        cif_data = [
            ['FOB Value:', f"{fob_value:,.2f} {currency}"],
            ['Freight:', f"{freight:,.2f} {currency}"],
            ['Insurance:', f"{insurance:,.2f} {currency}"],
            ['Other Charges:', f"{other_charges:,.2f} {currency}"],
            ['CIF (Foreign):', f"{cif_foreign:,.2f} {currency}"],
            ['CIF (PKR):', f"{cif_pkr:,.2f} PKR"],
        ]
        elements.append(self._create_data_table(cif_data, highlight_last=True))
        elements.append(Spacer(1, 0.2 * inch))

        # Duty Calculation Section
        elements.append(Paragraph("DUTY CALCULATION", self._styles['SectionHeader']))
        duty_data = [
            [f"Customs Duty ({customs_duty_rate}%):", f"{customs_duty_amount:,.2f} PKR"],
        ]

        if additional_duty_rate > 0:
            duty_data.append([f"Additional Duty ({additional_duty_rate}%):", f"{additional_duty_amount:,.2f} PKR"])

        if regulatory_duty_rate > 0:
            duty_data.append([f"Regulatory Duty ({regulatory_duty_rate}%):", f"{regulatory_duty_amount:,.2f} PKR"])

        if federal_excise_duty_rate > 0:
            duty_data.append([f"Federal Excise Duty ({federal_excise_duty_rate}%):", f"{federal_excise_duty_amount:,.2f} PKR"])

        duty_data.append([f"Sales Tax ({sales_tax_rate}%):", f"{sales_tax_amount:,.2f} PKR"])
        duty_data.append([f"Income Tax ({income_tax_rate}%):", f"{income_tax_amount:,.2f} PKR"])
        duty_data.append(['', ''])  # Separator
        duty_data.append(['Total Duties:', f"{total_duties:,.2f} PKR"])

        elements.append(self._create_data_table(duty_data, highlight_last=True))
        elements.append(Spacer(1, 0.3 * inch))

        # Total Section
        elements.append(self._create_total_box("TOTAL LANDED COST", f"{landed_cost:,.2f} PKR"))
        elements.append(Spacer(1, 0.3 * inch))

        # Data Source
        elements.append(Paragraph(
            f"<b>Data Sources:</b> Exchange Rate: {exchange_rate_source} | Duty Rates: {data_source}",
            self._styles['SmallText']
        ))

        # Disclaimer
        if self.config.include_disclaimer:
            elements.append(Spacer(1, 0.3 * inch))
            elements.append(self._create_disclaimer())

        # Footer
        if self.config.include_footer:
            elements.append(Spacer(1, 0.2 * inch))
            elements.append(self._create_footer())

        # Build PDF
        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue()

    def generate_export_report(
        self,
        hs_code: str,
        description: str,
        quantity: float,
        unit: str,
        fob_per_unit: float,
        currency: str,
        total_fob_foreign: float,
        exchange_rate: float,
        exchange_rate_source: str,
        total_fob_pkr: float,
        regulatory_duty_rate: float = 0,
        regulatory_duty_amount: float = 0,
        net_proceeds: float = 0,
        export_scheme: str = "Normal Export",
        destination: str = ""
    ) -> bytes:
        """
        Generate PDF for export proceeds calculation.

        Returns:
            PDF file as bytes
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=self.config.page_size,
            leftMargin=self.config.margin_left,
            rightMargin=self.config.margin_right,
            topMargin=self.config.margin_top,
            bottomMargin=self.config.margin_bottom
        )

        elements = []

        # Header
        elements.append(self._create_header("EXPORT PROCEEDS CALCULATION"))
        elements.append(Spacer(1, 0.2 * inch))

        # Document info
        info_data = [
            ['Date:', datetime.now().strftime('%Y-%m-%d %H:%M')],
            ['HS Code:', hs_code],
            ['Description:', description[:50] + '...' if len(description) > 50 else description],
            ['Destination:', destination or 'Not specified'],
            ['Export Scheme:', export_scheme],
        ]
        info_table = Table(info_data, colWidths=[1.5 * inch, 4 * inch])
        info_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(info_table)
        elements.append(Spacer(1, 0.3 * inch))

        # FOB Details Section
        elements.append(Paragraph("FOB VALUE", self._styles['SectionHeader']))
        fob_data = [
            ['Quantity:', f"{quantity:,.2f} {unit}"],
            ['FOB per Unit:', f"{fob_per_unit:,.2f} {currency}"],
            ['Total FOB:', f"{total_fob_foreign:,.2f} {currency}"],
            ['Exchange Rate:', f"{exchange_rate:,.4f} PKR/{currency} (TT Buying)"],
            ['Rate Source:', exchange_rate_source],
            ['FOB (PKR):', f"{total_fob_pkr:,.2f} PKR"],
        ]
        elements.append(self._create_data_table(fob_data, highlight_last=True))
        elements.append(Spacer(1, 0.2 * inch))

        # Duty Section
        elements.append(Paragraph("EXPORT DUTY", self._styles['SectionHeader']))
        if regulatory_duty_rate > 0:
            duty_data = [
                ['Export Duty:', '0 PKR (No export duty - Pakistan law)'],
                [f"Regulatory Duty ({regulatory_duty_rate}%):", f"{regulatory_duty_amount:,.2f} PKR"],
            ]
        else:
            duty_data = [
                ['Export Duty:', '0 PKR (No export duty - Pakistan law)'],
                ['Regulatory Duty:', '0 PKR (Not applicable)'],
            ]
        elements.append(self._create_data_table(duty_data))
        elements.append(Spacer(1, 0.3 * inch))

        # Total Section
        elements.append(self._create_total_box("NET EXPORT PROCEEDS", f"{net_proceeds:,.2f} PKR"))
        elements.append(Spacer(1, 0.3 * inch))

        # Notes
        elements.append(Paragraph("IMPORTANT NOTES", self._styles['SectionHeader']))
        notes = """
        <b>1. Export Duty:</b> Pakistan generally has NO export duty per law.<br/>
        <b>2. Regulatory Duty:</b> Only applies if specifically notified by FBR for your HS code.<br/>
        <b>3. Exchange Rate:</b> Uses TT Buying rate (bank buys your foreign currency).<br/>
        <b>4. Proceeds:</b> Must be repatriated within prescribed timeframe.
        """
        elements.append(Paragraph(notes, self._styles['Normal']))

        # Disclaimer
        if self.config.include_disclaimer:
            elements.append(Spacer(1, 0.3 * inch))
            elements.append(self._create_disclaimer())

        # Footer
        if self.config.include_footer:
            elements.append(Spacer(1, 0.2 * inch))
            elements.append(self._create_footer())

        # Build PDF
        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue()

    def _create_header(self, subtitle: str) -> Table:
        """Create header with title and subtitle"""
        data = [
            ['PAKISTAN CUSTOMS'],
            [subtitle]
        ]
        table = Table(data, colWidths=[5.5 * inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), self.HEADER_BG),
            ('TEXTCOLOR', (0, 0), (-1, 0), self.HEADER_TEXT),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 16),
            ('FONTSIZE', (0, 1), (-1, 1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOX', (0, 0), (-1, -1), 1, self.BORDER_COLOR),
        ]))
        return table

    def _create_data_table(self, data: list, highlight_last: bool = False) -> Table:
        """Create a two-column data table"""
        table = Table(data, colWidths=[2.5 * inch, 3 * inch])

        style_commands = [
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -1), 0.5, self.BORDER_COLOR),
        ]

        if highlight_last:
            style_commands.extend([
                ('BACKGROUND', (0, -1), (-1, -1), self.SECTION_BG),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ])

        table.setStyle(TableStyle(style_commands))
        return table

    def _create_total_box(self, label: str, value: str) -> Table:
        """Create highlighted total box"""
        data = [[label, value]]
        table = Table(data, colWidths=[2.5 * inch, 3 * inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), self.HEADER_BG),
            ('TEXTCOLOR', (0, 0), (-1, -1), self.HEADER_TEXT),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 14),
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ]))
        return table

    def _create_disclaimer(self) -> Paragraph:
        """Create disclaimer text"""
        disclaimer = """
        <b>DISCLAIMER:</b> This calculation is for reference only. Actual duties may vary
        based on current FBR notifications, SROs, and customs assessment. Please verify
        with official sources (WEBOC, FBR) before making business decisions.
        """
        return Paragraph(disclaimer, self._styles['SmallText'])

    def _create_footer(self) -> Paragraph:
        """Create footer"""
        footer = f"""
        Generated by RAG_HS_CODE System | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |
        Pakistan Customs Tariff FY 2024-25
        """
        style = ParagraphStyle(
            'Footer',
            parent=self._styles['SmallText'],
            alignment=TA_CENTER
        )
        return Paragraph(footer, style)


def generate_import_pdf(calculation_result: Dict[str, Any]) -> bytes:
    """
    Convenience function to generate import PDF from calculation result.

    Args:
        calculation_result: Dictionary from ImportDutyCalculator

    Returns:
        PDF as bytes
    """
    pdf = DutyCalculationPDF()
    return pdf.generate_import_report(
        hs_code=calculation_result.get('hs_code', 'N/A'),
        description=calculation_result.get('description', 'Import calculation'),
        quantity=calculation_result.get('quantity', 0),
        unit=calculation_result.get('unit_of_measure', 'units'),
        unit_value=calculation_result.get('unit_value_foreign', 0),
        currency=calculation_result.get('currency', 'USD'),
        exchange_rate=calculation_result.get('exchange_rate', 280),
        exchange_rate_source=calculation_result.get('exchange_rate_source', 'NBP'),
        fob_value=calculation_result.get('fob_value_foreign', 0),
        freight=calculation_result.get('freight_foreign', 0),
        insurance=calculation_result.get('insurance_foreign', 0),
        other_charges=calculation_result.get('other_charges_foreign', 0),
        cif_foreign=calculation_result.get('cif_value_foreign', 0),
        cif_pkr=calculation_result.get('cif_value_pkr', 0),
        customs_duty_rate=calculation_result.get('customs_duty_rate', 0),
        customs_duty_amount=calculation_result.get('customs_duty_amount', 0),
        additional_duty_rate=calculation_result.get('additional_duty_rate', 0),
        additional_duty_amount=calculation_result.get('additional_duty_amount', 0),
        regulatory_duty_rate=calculation_result.get('regulatory_duty_rate', 0),
        regulatory_duty_amount=calculation_result.get('regulatory_duty_amount', 0),
        federal_excise_duty_rate=calculation_result.get('federal_excise_duty_rate', 0),
        federal_excise_duty_amount=calculation_result.get('federal_excise_duty_amount', 0),
        sales_tax_rate=calculation_result.get('sales_tax_rate', 0),
        sales_tax_amount=calculation_result.get('sales_tax_amount', 0),
        income_tax_rate=calculation_result.get('income_tax_rate', 0),
        income_tax_amount=calculation_result.get('income_tax_amount', 0),
        total_duties=calculation_result.get('total_duties', 0),
        landed_cost=calculation_result.get('total_landed_cost', 0),
        data_source=calculation_result.get('data_source', 'WEBOC')
    )


if __name__ == "__main__":
    # Quick test
    print("Testing PDF Export...")

    pdf = DutyCalculationPDF()

    # Test import PDF
    import_pdf = pdf.generate_import_report(
        hs_code="0808.1000",
        description="Fresh apples",
        quantity=100,
        unit="kg",
        unit_value=10.0,
        currency="USD",
        exchange_rate=280.0,
        exchange_rate_source="NBP TT Selling",
        fob_value=1000.0,
        freight=0,
        insurance=0,
        other_charges=0,
        cif_foreign=1000.0,
        cif_pkr=280000.0,
        customs_duty_rate=20.0,
        customs_duty_amount=56000.0,
        sales_tax_rate=18.0,
        sales_tax_amount=60480.0,
        income_tax_rate=5.5,
        income_tax_amount=15400.0,
        total_duties=131880.0,
        landed_cost=411880.0
    )

    # Save test PDF
    with open('/tmp/test_import.pdf', 'wb') as f:
        f.write(import_pdf)

    print(f"  ✓ Import PDF generated: {len(import_pdf)} bytes")
    print("  ✓ Saved to /tmp/test_import.pdf")
