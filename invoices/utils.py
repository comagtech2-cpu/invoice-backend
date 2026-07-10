import io
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from django.http import HttpResponse
from .models import Invoice


def generate_invoice_pdf(invoice_id):
    """
    Generate a PDF for an invoice
    """
    try:
        # Get the invoice
        invoice = Invoice.objects.select_related('business').prefetch_related('line_items').get(id=invoice_id)
    except Invoice.DoesNotExist:
        return None

    # Create a file-like buffer to receive PDF data
    buffer = io.BytesIO()

    # Create the PDF object, using the buffer as its "file."
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []

    # Get styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=1  # Center alignment
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=12
    )

    # Header (logo + title)
    elements.append(Paragraph("INVOICE", title_style))
    elements.append(Spacer(1, 0.2*inch))

    # Invoice details
    invoice_data = [
        ['Invoice Number:', invoice.invoice_number],
        ['Issue Date:', invoice.issue_date.strftime('%B %d, %Y')],
        ['Due Date:', invoice.due_date.strftime('%B %d, %Y')],
        ['Status:', invoice.get_status_display()]
    ]
    
    invoice_table = Table(invoice_data, colWidths=[1.5*inch, 2*inch])
    invoice_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (1, 0), (-1, -1), 'LEFT'),
    ]))
    
    elements.append(invoice_table)
    elements.append(Spacer(1, 0.3*inch))

    # Business and client info
    business_info = [
        Paragraph(f"<b>{invoice.business.name}</b>", styles['Normal']),
    ]
    
    if invoice.business.address:
        business_info.append(Paragraph(invoice.business.address, styles['Normal']))
    
    if invoice.business.email:
        business_info.append(Paragraph(invoice.business.email, styles['Normal']))
    
    if invoice.business.phone_number:
        business_info.append(Paragraph(invoice.business.phone_number, styles['Normal']))
    
    # Add business info
    for item in business_info:
        elements.append(item)
    
    elements.append(Spacer(1, 0.3*inch))
    
    # Client info
    elements.append(Paragraph("<b>Bill To:</b>", heading_style))
    elements.append(Paragraph(f"<b>{invoice.client_name}</b>", styles['Normal']))
    
    if invoice.client_address:
        elements.append(Paragraph(invoice.client_address, styles['Normal']))
    
    if invoice.client_email:
        elements.append(Paragraph(invoice.client_email, styles['Normal']))
    
    if invoice.client_phone:
        elements.append(Paragraph(invoice.client_phone, styles['Normal']))
    
    elements.append(Spacer(1, 0.3*inch))

    # Line items table
    elements.append(Paragraph("<b>Items</b>", heading_style))
    
    # Table header
    table_data = [['Description', 'Quantity', 'Unit Price', 'Total']]
    
    # Add line items
    for item in invoice.line_items.all():
        table_data.append([
            item.description,
            str(item.quantity),
            f"${item.unit_price:.2f}",
            f"${item.total_price:.2f}"
        ])
    
    # Add summary row
    table_data.append(['', '', 'Subtotal:', f"${invoice.subtotal:.2f}"])
    table_data.append(['', '', f'Tax ({invoice.tax_rate}%):', f"${invoice.tax_amount:.2f}"])
    table_data.append(['', '', 'Total:', f"${invoice.total_amount:.2f}"])

    # Create table
    table = Table(table_data, colWidths=[3*inch, 0.8*inch, 1*inch, 1*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -2), 1, colors.black),
        ('SPAN', (-2, -3), (-1, -3)),  # Subtotal row
        ('SPAN', (-2, -2), (-1, -2)),  # Tax row
        ('SPAN', (-2, -1), (-1, -1)),  # Total row
        ('ALIGN', (-1, -3), (-1, -1), 'RIGHT'),  # Right align totals
        ('FONTNAME', (-1, -3), (-1, -1), 'Helvetica-Bold'),  # Bold totals
    ]))
    
    elements.append(table)
    elements.append(Spacer(1, 0.3*inch))

    # Notes
    if invoice.notes:
        elements.append(Paragraph("<b>Notes:</b>", heading_style))
        elements.append(Paragraph(invoice.notes, styles['Normal']))

    # Build PDF
    doc.build(elements)

    # Get the value of the BytesIO buffer and write it to the response
    pdf = buffer.getvalue()
    buffer.close()
    
    return pdf