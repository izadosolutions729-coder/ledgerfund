import io
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from django.utils import timezone
from ledger.models import LedgerEntry
from core.models import Organization
from decimal import Decimal

class ReportingEngine:
    @staticmethod
    def generate_general_ledger_report(organization: Organization, start_date=None, end_date=None):
        queryset = LedgerEntry.objects.filter(organization=organization).order_by('transaction_date', 'id')
        if start_date:
            queryset = queryset.filter(transaction_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(transaction_date__lte=end_date)
            
        return queryset

class PDFExportSystem:
    @staticmethod
    def export_general_ledger_pdf(organization: Organization, start_date=None, end_date=None, generated_by=None):
        entries = ReportingEngine.generate_general_ledger_report(organization, start_date, end_date)
        
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        elements = []
        styles = getSampleStyleSheet()
        
        # Header
        elements.append(Paragraph(f"<b>{organization.organization_name}</b>", styles['Heading1']))
        elements.append(Paragraph("General Ledger Report", styles['Heading2']))
        period = f"Period: {start_date or 'All'} to {end_date or 'All'}"
        elements.append(Paragraph(period, styles['Normal']))
        
        timestamp = f"Generated at: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}"
        if generated_by:
            timestamp += f" by {generated_by.username}"
        elements.append(Paragraph(timestamp, styles['Normal']))
        elements.append(Spacer(1, 12))
        
        # Data Table
        data = [['Date', 'Category', 'Type', 'Debit', 'Credit', 'Balance', 'Remarks']]
        total_debit = Decimal('0.00')
        total_credit = Decimal('0.00')
        
        for entry in entries:
            data.append([
                entry.transaction_date.strftime('%Y-%m-%d'),
                entry.category,
                entry.transaction_type.capitalize(),
                f"{entry.debit_amount:.2f}",
                f"{entry.credit_amount:.2f}",
                f"{entry.balance_after_transaction:.2f}",
                entry.remarks or ""
            ])
            total_debit += entry.debit_amount
            total_credit += entry.credit_amount
            
        data.append(['', 'TOTAL', '', f"{total_debit:.2f}", f"{total_credit:.2f}", '', ''])
        
        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        
        elements.append(table)
        doc.build(elements)
        
        return buffer.getvalue()
