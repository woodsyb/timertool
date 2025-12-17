"""Generate professional PDF invoices using reportlab."""

import sys
from pathlib import Path
from datetime import datetime

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

import db


def generate_invoice_pdf(invoice_number: str) -> Path:
    """Generate PDF for an invoice, return path to file."""
    if not REPORTLAB_AVAILABLE:
        raise ImportError("reportlab is required for PDF generation. Install with: pip install reportlab")

    invoice = db.get_invoice(invoice_number)
    if not invoice:
        raise ValueError(f"Invoice {invoice_number} not found")

    business = db.get_business_info()
    if not business:
        raise ValueError("Business info not configured. Go to Edit > Business Setup.")

    banking = db.get_banking()
    if not banking:
        raise ValueError("Banking info not configured. Go to Edit > Business Setup.")

    # Organize by client name
    client_folder = db.get_pdfs_dir() / invoice['client_name'].replace(' ', '_')
    client_folder.mkdir(exist_ok=True)
    output_path = client_folder / f"{invoice_number}.pdf"
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.5*inch,
        bottomMargin=0.5*inch
    )

    styles = getSampleStyleSheet()

    # Custom styles
    styles.add(ParagraphStyle(
        'CompanyName',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=6,
        textColor=colors.HexColor('#1a1a1a')
    ))

    styles.add(ParagraphStyle(
        'CompanyInfo',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#666666'),
        leading=12
    ))

    styles.add(ParagraphStyle(
        'InvoiceTitle',
        parent=styles['Heading1'],
        fontSize=28,
        alignment=TA_RIGHT,
        textColor=colors.HexColor('#333333')
    ))

    styles.add(ParagraphStyle(
        'SectionHeader',
        parent=styles['Heading2'],
        fontSize=11,
        spaceBefore=12,
        spaceAfter=6,
        textColor=colors.HexColor('#333333')
    ))

    styles.add(ParagraphStyle(
        'ClientInfo',
        parent=styles['Normal'],
        fontSize=10,
        leading=14
    ))

    styles.add(ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=9,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#666666')
    ))

    styles.add(ParagraphStyle(
        'PaymentInfo',
        parent=styles['Normal'],
        fontSize=10,
        leading=14
    ))

    elements = []

    # Header section with company info and INVOICE title
    header_data = [
        [
            Paragraph(business['company_name'], styles['CompanyName']),
            Paragraph('INVOICE', styles['InvoiceTitle'])
        ],
        [
            Paragraph(
                f"{business['address']}<br/>"
                f"{business['city']}, {business['state']} {business['zip']}<br/>"
                f"{business['phone']}<br/>"
                f"{business['email']}",
                styles['CompanyInfo']
            ),
            ''
        ]
    ]

    header_table = Table(header_data, colWidths=[4*inch, 3*inch])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 0.3*inch))

    # Invoice details and Bill To section
    invoice_details = [
        ['Invoice Number:', invoice['invoice_number']],
        ['Date Issued:', db.format_date_display(invoice['date_issued'])],
        ['Due Date:', db.format_date_display(invoice['due_date'])],
        ['Payment Terms:', invoice['payment_terms']],
    ]

    invoice_table = Table(invoice_details, colWidths=[1.2*inch, 1.8*inch])
    invoice_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#666666')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
    ]))

    # Build client info
    client_lines = [
        "<b>Bill To:</b>",
        invoice['client_name'],
    ]
    if invoice.get('contact_name'):
        client_lines.append(invoice['contact_name'])
    if invoice.get('client_address'):
        client_lines.append(invoice['client_address'])
    if invoice.get('client_city') or invoice.get('client_state') or invoice.get('client_zip'):
        city_state_zip = ', '.join(filter(None, [
            invoice.get('client_city'),
            ' '.join(filter(None, [invoice.get('client_state'), invoice.get('client_zip')]))
        ]))
        if city_state_zip:
            client_lines.append(city_state_zip)

    client_info = Paragraph('<br/>'.join(client_lines), styles['ClientInfo'])

    details_row = Table([[invoice_table, client_info]], colWidths=[3.5*inch, 3.5*inch])
    details_row.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    elements.append(details_row)
    elements.append(Spacer(1, 0.4*inch))

    # Line items table - hourly billing with daily breakdown
    daily_hours = db.get_invoice_hours(invoice['invoice_number'])
    if daily_hours:
        elements.append(Paragraph(f"<b>{invoice['description']}</b> - {db.format_currency(invoice['rate'])}/hr", styles['Normal']))
        elements.append(Spacer(1, 0.05*inch))
        line_items = [['Date', 'Hours', 'Amount']]
        for entry in daily_hours:
            dt = datetime.fromisoformat(entry['work_date'])
            date_str = dt.strftime('%a %b %d')
            hrs = entry['hours']
            amt = hrs * invoice['rate']
            line_items.append([date_str, f"{hrs:.2f}", db.format_currency(amt)])
        line_items.append(['Total', f"{invoice['quantity']:.2f}", db.format_currency(invoice['total'])])
        col_widths = [2.5*inch, 1.5*inch, 3*inch]
    else:
        line_items = [
            ['Description', 'Rate', 'Hours', 'Amount'],
            [invoice['description'], db.format_currency(invoice['rate']), f"{invoice['quantity']:.2f}", db.format_currency(invoice['total'])]
        ]
        col_widths = [3.5*inch, 1.25*inch, 1*inch, 1.25*inch]

    items_table = Table(line_items, colWidths=col_widths)
    table_style = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f5f5f5')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('LINEBELOW', (0, 0), (-1, 0), 1, colors.HexColor('#dddddd')),
        ('LINEBELOW', (0, -1), (-1, -1), 1, colors.HexColor('#dddddd')),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
    ]
    if daily_hours:
        table_style.append(('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'))
        table_style.append(('LINEABOVE', (0, -1), (-1, -1), 1, colors.HexColor('#dddddd')))
    items_table.setStyle(TableStyle(table_style))
    elements.append(items_table)
    elements.append(Spacer(1, 0.15*inch))

    # Payment instructions
    elements.append(Paragraph('Payment Instructions', styles['SectionHeader']))

    if invoice['payment_method'] == 'ACH':
        payment_text = (
            f"<b>ACH Transfer</b><br/>"
            f"Bank: {banking['bank_name']}<br/>"
            f"Routing Number: {banking['routing_number']}<br/>"
            f"Account Number: {banking['account_number']}"
        )
    elif invoice['payment_method'] == 'Wire':
        wire_info = banking.get('wire_instructions') or (
            f"Bank: {banking['bank_name']}\n"
            f"Routing: {banking['routing_number']}\n"
            f"Account: {banking['account_number']}"
        )
        payment_text = f"<b>Wire Transfer</b><br/>{wire_info.replace(chr(10), '<br/>')}"
    else:
        payment_text = (
            f"<b>Check</b><br/>"
            f"Make payable to: {business['company_name']}<br/>"
            f"Mail to: {business['address']}, {business['city']}, {business['state']} {business['zip']}"
        )

    elements.append(Paragraph(payment_text, styles['PaymentInfo']))
    elements.append(Spacer(1, 0.25*inch))

    # Footer
    elements.append(Paragraph(
        f"Thank you for your business!<br/>"
        f"EIN: {business['ein']}",
        styles['Footer']
    ))

    doc.build(elements)
    return output_path
