from django.urls import path
from .views import (
    InvoiceListCreateView, InvoiceDetailView, DashboardSummaryView, ReportView,
    ReceiptListCreateView, ReceiptDetailView, RecurringInvoiceListCreateView, RecurringInvoiceDetailView,
    ReminderRuleListCreateView, ReminderRuleDetailView, InvoiceTemplateListCreateView, InvoiceTemplateDetailView
)

urlpatterns = [
    path('invoices/', InvoiceListCreateView.as_view(), name='invoice-list-create'),
    path('invoices/<int:pk>/', InvoiceDetailView.as_view(), name='invoice-detail'),
    path('recurring-invoices/', RecurringInvoiceListCreateView.as_view(), name='recurring-list-create'),
    path('recurring-invoices/<int:pk>/', RecurringInvoiceDetailView.as_view(), name='recurring-detail'),
    path('reminder-rules/', ReminderRuleListCreateView.as_view(), name='reminder-rule-list-create'),
    path('reminder-rules/<int:pk>/', ReminderRuleDetailView.as_view(), name='reminder-rule-detail'),
    path('invoice-templates/', InvoiceTemplateListCreateView.as_view(), name='invoice-template-list-create'),
    path('invoice-templates/<int:pk>/', InvoiceTemplateDetailView.as_view(), name='invoice-template-detail'),
    path('dashboard/summary/', DashboardSummaryView.as_view(), name='dashboard-summary'),
    path('reports/', ReportView.as_view(), name='reports'),
    path('receipts/', ReceiptListCreateView.as_view(), name='receipt-list-create'),
    path('receipts/<int:pk>/', ReceiptDetailView.as_view(), name='receipt-detail'),
]