import csv
import io
import logging
from django.shortcuts import render
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from datetime import datetime
from .models import Invoice, Receipt, RecurringInvoice, InvoiceTemplate
from .serializers import (
    InvoiceSerializer, DashboardSummarySerializer, ReportSerializer,
    FinancialReportSerializer, InvoiceReportSerializer, ReceiptSerializer,
    RecurringInvoiceSerializer, ReminderRuleSerializer, InvoiceTemplateSerializer
)
from .utils import generate_invoice_pdf
from business.models import Business, Client


class RecurringInvoiceListCreateView(APIView):
    def get(self, request):
        business_filter = request.GET.get('business')
        queryset = RecurringInvoice.objects.filter(business__created_by=request.user)
        if business_filter:
            queryset = queryset.filter(business_id=business_filter)
        serializer = RecurringInvoiceSerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request):
        # Verify business ownership
        business_id = request.data.get('business')
        try:
            business = Business.objects.get(pk=business_id, created_by=request.user)
        except Business.DoesNotExist:
            return Response({'error': 'Business not found or not owned by user'}, status=status.HTTP_404_NOT_FOUND)

        # Verify client belongs to business
        client_id = request.data.get('client')
        try:
            client = Client.objects.get(pk=client_id, business=business)
        except Client.DoesNotExist:
            return Response({'error': 'Client not found for this business'}, status=status.HTTP_404_NOT_FOUND)

        serializer = RecurringInvoiceSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(created_by=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RecurringInvoiceDetailView(APIView):
    def get(self, request, pk):
        try:
            ri = RecurringInvoice.objects.get(pk=pk, business__created_by=request.user)
            serializer = RecurringInvoiceSerializer(ri)
            return Response(serializer.data)
        except RecurringInvoice.DoesNotExist:
            return Response({'error': 'Recurring invoice not found'}, status=status.HTTP_404_NOT_FOUND)

    def put(self, request, pk):
        try:
            ri = RecurringInvoice.objects.get(pk=pk, business__created_by=request.user)
            serializer = RecurringInvoiceSerializer(ri, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except RecurringInvoice.DoesNotExist:
            return Response({'error': 'Recurring invoice not found'}, status=status.HTTP_404_NOT_FOUND)

    def delete(self, request, pk):
        try:
            ri = RecurringInvoice.objects.get(pk=pk, business__created_by=request.user)
            ri.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except RecurringInvoice.DoesNotExist:
            return Response({'error': 'Recurring invoice not found'}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request, pk):
        # Allow manual trigger via POST
        action = request.data.get('action')
        if action != 'generate':
            return Response({'error': 'Unknown action'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            ri = RecurringInvoice.objects.get(pk=pk, business__created_by=request.user)
        except RecurringInvoice.DoesNotExist:
            return Response({'error': 'Recurring invoice not found'}, status=status.HTTP_404_NOT_FOUND)

        # Generate a single invoice immediately
        from django.core.management import call_command
        try:
            call_command('generate_recurring_invoices', '--id', str(ri.id))
            return Response({'message': 'Generation triggered'})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ReminderRuleListCreateView(APIView):
    def get(self, request):
        business_filter = request.GET.get('business')
        queryset = ReminderRule.objects.filter(business__created_by=request.user)
        if business_filter:
            queryset = queryset.filter(business_id=business_filter)
        serializer = ReminderRuleSerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request):
        business_id = request.data.get('business')
        try:
            business = Business.objects.get(pk=business_id, created_by=request.user)
        except Business.DoesNotExist:
            return Response({'error': 'Business not found or not owned by user'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ReminderRuleSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(created_by=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ReminderRuleDetailView(APIView):
    def get(self, request, pk):
        try:
            rule = ReminderRule.objects.get(pk=pk, business__created_by=request.user)
            serializer = ReminderRuleSerializer(rule)
            return Response(serializer.data)
        except ReminderRule.DoesNotExist:
            return Response({'error': 'ReminderRule not found'}, status=status.HTTP_404_NOT_FOUND)

    def put(self, request, pk):
        try:
            rule = ReminderRule.objects.get(pk=pk, business__created_by=request.user)
            serializer = ReminderRuleSerializer(rule, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except ReminderRule.DoesNotExist:
            return Response({'error': 'ReminderRule not found'}, status=status.HTTP_404_NOT_FOUND)

    def delete(self, request, pk):
        try:
            rule = ReminderRule.objects.get(pk=pk, business__created_by=request.user)
            rule.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ReminderRule.DoesNotExist:
            return Response({'error': 'ReminderRule not found'}, status=status.HTTP_404_NOT_FOUND)


class InvoiceTemplateListCreateView(APIView):
    def get(self, request):
        business_filter = request.GET.get('business')
        queryset = InvoiceTemplate.objects.filter(business__created_by=request.user)
        if business_filter:
            queryset = queryset.filter(business_id=business_filter)
        serializer = InvoiceTemplateSerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request):
        business_id = request.data.get('business')
        try:
            business = Business.objects.get(pk=business_id, created_by=request.user)
        except Business.DoesNotExist:
            return Response({'error': 'Business not found or not owned by user'}, status=status.HTTP_404_NOT_FOUND)

        serializer = InvoiceTemplateSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(created_by=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        logger.error('Invoice template create errors: %s', serializer.errors)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class InvoiceTemplateDetailView(APIView):
    def get(self, request, pk):
        try:
            tmpl = InvoiceTemplate.objects.get(pk=pk, business__created_by=request.user)
            serializer = InvoiceTemplateSerializer(tmpl)
            return Response(serializer.data)
        except InvoiceTemplate.DoesNotExist:
            return Response({'error': 'InvoiceTemplate not found'}, status=status.HTTP_404_NOT_FOUND)

    def put(self, request, pk):
        try:
            tmpl = InvoiceTemplate.objects.get(pk=pk, business__created_by=request.user)
            serializer = InvoiceTemplateSerializer(tmpl, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except InvoiceTemplate.DoesNotExist:
            return Response({'error': 'InvoiceTemplate not found'}, status=status.HTTP_404_NOT_FOUND)

    def delete(self, request, pk):
        try:
            tmpl = InvoiceTemplate.objects.get(pk=pk, business__created_by=request.user)
            tmpl.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except InvoiceTemplate.DoesNotExist:
            return Response({'error': 'InvoiceTemplate not found'}, status=status.HTTP_404_NOT_FOUND)
from rest_framework.pagination import PageNumberPagination

logger = logging.getLogger(__name__)


class InvoicePagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class DashboardSummaryView(APIView):
    def get(self, request):
        # Get all invoices for the user
        invoices = Invoice.objects.filter(created_by=request.user)
        
        # Calculate key metrics
        total_invoices = invoices.count()
        total_revenue = invoices.filter(status='paid').aggregate(
            total=Sum('total_amount')
        )['total'] or 0
        
        pending_invoices = invoices.filter(status='sent').count()
        paid_invoices = invoices.filter(status='paid').count()
        overdue_invoices = invoices.filter(
            status='sent',
            due_date__lt=timezone.now().date()
        ).count()
        
        # Prepare data for serialization
        summary_data = {
            'total_invoices': total_invoices,
            'total_revenue': total_revenue,
            'pending_invoices': pending_invoices,
            'paid_invoices': paid_invoices,
            'overdue_invoices': overdue_invoices,
        }
        
        serializer = DashboardSummarySerializer(summary_data)
        return Response(serializer.data)


class ReportView(APIView):
    def get(self, request):
        # Check if CSV export is requested
        if request.GET.get('format') == 'csv':
            return self.export_csv(request)
        
        # Validate query parameters
        serializer = ReportSerializer(data=request.GET)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Get filtered invoices with business relationship
        invoices = self._get_filtered_invoices(request.user, serializer.validated_data).select_related('business')
        
        # Generate financial report data (monthly breakdown)
        financial_data = self._generate_financial_report(invoices)
        
        # Serialize invoice data
        invoice_serializer = InvoiceReportSerializer(invoices, many=True)
        
        return Response({
            'financial_report': financial_data,
            'invoices': invoice_serializer.data
        })
    
    def export_csv(self, request):
        # Validate query parameters
        serializer = ReportSerializer(data=request.GET)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Get filtered invoices with business relationship
        invoices = self._get_filtered_invoices(request.user, serializer.validated_data).select_related('business')
        
        # Create CSV response
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="invoices_report.csv"'
        
        # Create CSV writer
        writer = csv.writer(response)
        
        # Write header
        writer.writerow([
            'Invoice Number', 'Client Name', 'Business Name', 
            'Issue Date', 'Due Date', 'Status', 'Total Amount'
        ])
        
        # Write data rows
        for invoice in invoices:
            writer.writerow([
                invoice.invoice_number,
                invoice.client_name,
                invoice.business.name,
                invoice.issue_date,
                invoice.due_date,
                invoice.status,
                invoice.total_amount
            ])
        
        return response
    
    def _get_filtered_invoices(self, user, filters):
        invoices = Invoice.objects.filter(created_by=user).select_related('business')
        
        # Apply date filters
        if filters.get('start_date'):
            invoices = invoices.filter(issue_date__gte=filters['start_date'])
        
        if filters.get('end_date'):
            invoices = invoices.filter(issue_date__lte=filters['end_date'])
        
        # Apply status filter (case-insensitive)
        if filters.get('status'):
            invoices = invoices.filter(status__iexact=filters['status'])
        
        # Apply business filter
        if filters.get('business_id'):
            invoices = invoices.filter(business_id=filters['business_id'])
        
        return invoices
    
    def _generate_financial_report(self, invoices):
        # Group invoices by month and calculate revenue
        monthly_data = {}
        
        for invoice in invoices:
            # Only count paid invoices in revenue
            if invoice.status != 'paid':
                continue
                
            # Group by year-month
            month_key = invoice.issue_date.strftime('%Y-%m')
            if month_key not in monthly_data:
                monthly_data[month_key] = {
                    'period': month_key,
                    'revenue': 0,
                    'invoices_count': 0
                }
            
            monthly_data[month_key]['revenue'] += float(invoice.total_amount)
            monthly_data[month_key]['invoices_count'] += 1
        
        # Convert to list and sort by period
        financial_data = list(monthly_data.values())
        financial_data.sort(key=lambda x: x['period'])
        
        # Serialize data
        serializer = FinancialReportSerializer(financial_data, many=True)
        return serializer.data


class InvoiceListCreateView(APIView):
    def get(self, request):
        # Get query parameters
        search = request.GET.get('search', '')
        status_filter = request.GET.get('status', '')
        business_filter = request.GET.get('business', '')
        sort_by = request.GET.get('sort_by', '-created_at')
        
        # Start with all invoices for the user
        invoices = Invoice.objects.filter(created_by=request.user)
        
        # Apply filters
        if search:
            invoices = invoices.filter(
                Q(client_name__icontains=search) |
                Q(invoice_number__icontains=search) |
                Q(notes__icontains=search)
            )
        
        if status_filter:
            # Accept status case-insensitively from query params
            invoices = invoices.filter(status__iexact=status_filter)
            
        if business_filter:
            invoices = invoices.filter(business_id=business_filter)
        
        # Apply sorting
        allowed_sort_fields = ['created_at', '-created_at', 'due_date', '-due_date', 'total_amount', '-total_amount']
        if sort_by in allowed_sort_fields:
            invoices = invoices.order_by(sort_by)
        else:
            invoices = invoices.order_by('-created_at')
        
        # Apply pagination
        paginator = InvoicePagination()
        paginated_invoices = paginator.paginate_queryset(invoices, request)
        serializer = InvoiceSerializer(paginated_invoices, many=True, context={'request': request})
        
        return paginator.get_paginated_response(serializer.data)
    
    def post(self, request):
        # Verify that the business belongs to the user
        business_id = request.data.get('business')
        try:
            business = Business.objects.get(id=business_id, created_by=request.user)
        except Business.DoesNotExist:
            return Response(
                {'error': 'Business not found or does not belong to you'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = InvoiceSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save(created_by=request.user)
            # Re-serialize to ensure fields like business_logo_url are present
            serializer = InvoiceSerializer(serializer.instance, context={'request': request})
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class InvoiceDetailView(APIView):
    def get(self, request, pk):
        # Debug log request context for troubleshooting 404 on PDF downloads
        logger.debug(f"InvoiceDetailView.get called: user={request.user}, pk={pk}, format={request.GET.get('format')}")

        # Check if PDF download is requested
        if request.GET.get('format') == 'pdf':
            return self.download_pdf(request, pk)
        
        try:
            invoice = Invoice.objects.get(pk=pk, created_by=request.user)
            serializer = InvoiceSerializer(invoice, context={'request': request})
            return Response(serializer.data)
        except Invoice.DoesNotExist:
            logger.warning(f"Invoice not found: user={request.user}, pk={pk}")
            return Response({'error': 'Invoice not found'}, status=status.HTTP_404_NOT_FOUND)
    
    def download_pdf(self, request, pk):
        logger.debug(f"download_pdf called: user={request.user}, pk={pk}")
        try:
            invoice = Invoice.objects.get(pk=pk, created_by=request.user)
            logger.debug(f"invoice found for download: id={invoice.id}, owner={invoice.created_by}")
        except Invoice.DoesNotExist:
            logger.warning(f"download_pdf: invoice not found or not owned by user: user={request.user}, pk={pk}")
            return Response({'error': 'Invoice not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Generate PDF
        pdf_buffer = generate_invoice_pdf(invoice.id)
        
        if pdf_buffer is None:
            logger.error(f"Failed to generate PDF for invoice id={invoice.id}")
            return Response({'error': 'Failed to generate PDF'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # Create HTTP response with PDF
        response = HttpResponse(pdf_buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="invoice_{invoice.invoice_number}.pdf"'
        
        return response
    
    def send_invoice(self, request, pk):
        try:
            invoice = Invoice.objects.select_related('business').get(pk=pk, created_by=request.user)
        except Invoice.DoesNotExist:
            return Response({'error': 'Invoice not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Check if client email is provided
        if not invoice.client_email:
            return Response({'error': 'Client email is not provided'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Prepare email context
        frontend_url = 'http://localhost:3000'  # Adjust this to your frontend URL
        context = {
            'business_name': invoice.business.name,
            'business_email': invoice.business.email or '',
            'business_address': invoice.business.address or '',
            'invoice_number': invoice.invoice_number,
            'issue_date': invoice.issue_date.strftime('%B %d, %Y'),
            'due_date': invoice.due_date.strftime('%B %d, %Y'),
            'total_amount': f'{invoice.total_amount:.2f}',
            'client_name': invoice.client_name,
            'invoice_url': f'{frontend_url}/invoices/{invoice.id}'
        }
        
        # Render email templates
        subject = f'New Invoice from {invoice.business.name} - {invoice.invoice_number}'
        text_content = render_to_string('emails/invoice_notification.txt', context)
        html_content = render_to_string('emails/invoice_notification.html', context)
        
        # Create and send email
        msg = EmailMultiAlternatives(
            subject,
            text_content,
            settings.DEFAULT_FROM_EMAIL,
            [invoice.client_email]
        )
        msg.attach_alternative(html_content, 'text/html')
        
        # Attach PDF invoice
        pdf_buffer = generate_invoice_pdf(invoice.id)
        if pdf_buffer:
            msg.attach(f'invoice_{invoice.invoice_number}.pdf', pdf_buffer, 'application/pdf')
        
        try:
            msg.send()
            # Update invoice status to 'sent'
            if invoice.status == 'draft':
                invoice.status = 'sent'
                invoice.save()
            return Response({'message': 'Invoice sent successfully'})
        except Exception as e:
            return Response({'error': f'Failed to send invoice: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def put(self, request, pk):
        try:
            invoice = Invoice.objects.get(pk=pk, created_by=request.user)
            
            # Verify that the business belongs to the user
            business_id = request.data.get('business')
            if business_id:
                try:
                    business = Business.objects.get(id=business_id, created_by=request.user)
                except Business.DoesNotExist:
                    return Response(
                        {'error': 'Business not found or does not belong to you'}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            serializer = InvoiceSerializer(invoice, data=request.data, partial=True, context={'request': request})
            if serializer.is_valid():
                serializer.save()
                # Re-serialize updated instance to include computed fields
                serializer = InvoiceSerializer(serializer.instance, context={'request': request})
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Invoice.DoesNotExist:
            return Response({'error': 'Invoice not found'}, status=status.HTTP_404_NOT_FOUND)
    
    def delete(self, request, pk):
        try:
            invoice = Invoice.objects.get(pk=pk, created_by=request.user)
            invoice.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Invoice.DoesNotExist:
            return Response({'error': 'Invoice not found'}, status=status.HTTP_404_NOT_FOUND)


class ReceiptListCreateView(APIView):
    def get(self, request):
        # Get query parameters
        search = request.GET.get('search', '')
        sort_by = request.GET.get('sort_by', '-created_at')

        # Start with all receipts for the user
        receipts = Receipt.objects.filter(created_by=request.user).select_related('invoice__business')

        # Apply search filter
        if search:
            receipts = receipts.filter(
                Q(receipt_number__icontains=search) |
                Q(invoice__invoice_number__icontains=search) |
                Q(invoice__client_name__icontains=search)
            )

        # Apply sorting
        allowed_sort_fields = ['created_at', '-created_at', 'payment_date', '-payment_date', 'amount_paid', '-amount_paid']
        if sort_by in allowed_sort_fields:
            receipts = receipts.order_by(sort_by)
        else:
            receipts = receipts.order_by('-created_at')

        # Apply pagination
        paginator = InvoicePagination()
        paginated_receipts = paginator.paginate_queryset(receipts, request)
        serializer = ReceiptSerializer(paginated_receipts, many=True, context={'request': request})

        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        # Verify that the invoice belongs to the user. If it's not marked paid,
        # allow creating a receipt and auto-mark the invoice as paid.
        invoice_id = request.data.get('invoice')
        try:
            invoice = Invoice.objects.get(id=invoice_id, created_by=request.user)
        except Invoice.DoesNotExist:
            return Response(
                {'error': 'Invoice not found or does not belong to you'},
                status=status.HTTP_404_NOT_FOUND
            )

        # If invoice is not paid, mark it paid now so receipt can be created
        if invoice.status != 'paid':
            invoice.status = 'paid'
            invoice.save()

        # Check if receipt already exists for this invoice
        if hasattr(invoice, 'receipt'):
            return Response(
                {'error': 'Receipt already exists for this invoice'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = ReceiptSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response({
                'errors': serializer.errors,
                'request_data': request.data,
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            receipt = serializer.save(created_by=request.user)
            return Response(ReceiptSerializer(receipt, context={'request': request}).data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({
                'error': 'Failed to save receipt',
                'exception': str(e),
                'request_data': request.data,
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ReceiptDetailView(APIView):
    def get(self, request, pk):
        try:
            receipt = Receipt.objects.select_related('invoice__business').get(pk=pk, created_by=request.user)
            serializer = ReceiptSerializer(receipt, context={'request': request})
            return Response(serializer.data)
        except Receipt.DoesNotExist:
            return Response({'error': 'Receipt not found'}, status=status.HTTP_404_NOT_FOUND)

    def put(self, request, pk):
        try:
            receipt = Receipt.objects.get(pk=pk, created_by=request.user)
            serializer = ReceiptSerializer(receipt, data=request.data, partial=True, context={'request': request})
            if serializer.is_valid():
                serializer.save()
                # reserialize
                serializer = ReceiptSerializer(serializer.instance, context={'request': request})
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Receipt.DoesNotExist:
            return Response({'error': 'Receipt not found'}, status=status.HTTP_404_NOT_FOUND)

    def delete(self, request, pk):
        try:
            receipt = Receipt.objects.get(pk=pk, created_by=request.user)
            receipt.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Receipt.DoesNotExist:
            return Response({'error': 'Receipt not found'}, status=status.HTTP_404_NOT_FOUND)