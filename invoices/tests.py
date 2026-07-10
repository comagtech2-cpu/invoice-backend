from django.test import TestCase
from rest_framework.test import APIClient
from django.core.management import call_command
from django.utils import timezone
from accounts.models import User
from business.models import Business, Client
from .models import RecurringInvoice, Invoice, ReminderRule
from datetime import date


class RecurringInvoiceTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='ruser', email='r@example.com', password='password')
        self.business = Business.objects.create(name='Recurring Biz', created_by=self.user)
        self.client = Client.objects.create(business=self.business, name='Sub Corp')

    def test_generate_recurring_invoice_creates_invoice(self):
        today = timezone.now().date()
        ri = RecurringInvoice.objects.create(
            business=self.business,
            client=self.client,
            frequency='monthly',
            interval=1,
            start_date=today,
            next_run_date=today,
            template={'line_items': [{'description': 'Service', 'quantity': 1, 'unit_price': 100}]},
            created_by=self.user
        )

        call_command('generate_recurring_invoices')
        invoices = Invoice.objects.filter(business=self.business)
        self.assertEqual(invoices.count(), 1)
        inv = invoices.first()
        self.assertEqual(str(inv.total_amount), '100.00')
        ri.refresh_from_db()
        self.assertTrue(ri.last_generated_at is not None)
        self.assertNotEqual(ri.next_run_date, today)


from django.core import mail
from django.test.utils import override_settings
from django.core.management import call_command


class ReminderTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='remuser', email='rem@example.com', password='password')
        self.business = Business.objects.create(name='Rem Biz', created_by=self.user)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_send_due_reminder(self):
        today = timezone.now().date()
        inv = Invoice.objects.create(
            invoice_number='INV-TEST',
            business=self.business,
            client_name='Client X',
            client_email='clientx@example.com',
            issue_date=today, due_date=today,
            subtotal=100, tax_rate=0, tax_amount=0, total_amount=100,
            created_by=self.user,
            status='sent'
        )
        rule = ReminderRule.objects.create(
            business=self.business,
            invoice=inv,
            days_before_due=0,
            subject_template='Reminder for {{ invoice.invoice_number }}',
            text_template='Please pay {{ invoice.invoice_number }}',
            created_by=self.user,
        )

        # Run management command
        call_command('send_due_reminders')

        # Check outbox
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertIn('Reminder', message.subject)
        self.assertIn('clientx@example.com', message.to)


    def test_receipt_includes_currency(self):
        client = APIClient()
        client.force_authenticate(user=self.user)
        today = timezone.now().date()

        inv = Invoice.objects.create(
            invoice_number='CUR-1',
            business=self.business,
            client_name='Cur Client',
            issue_date=today, due_date=today,
            subtotal=50, tax_rate=0, tax_amount=0, total_amount=50,
            created_by=self.user,
            status='paid',
            currency='EUR'
        )

        # Create receipt via API to ensure serializer fields
        resp = client.post('/api/receipts/', {
            'invoice': inv.id,
            'payment_date': today,
            'payment_method': 'cash',
            'amount_paid': 50,
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        rid = resp.data['id']
        # Fetch receipt and ensure currency is present
        resp = client.get(f'/api/receipts/{rid}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data.get('currency'), 'EUR')

    def test_invoice_list_server_side_filters(self):
        client = APIClient()
        client.force_authenticate(user=self.user)
        today = timezone.now().date()

        # Create invoices with different statuses and invoice numbers
        inv_draft = Invoice.objects.create(
            invoice_number='DRAFT-1',
            business=self.business,
            client_name='Draft Client',
            issue_date=today, due_date=today,
            subtotal=10, tax_rate=0, tax_amount=0, total_amount=10,
            created_by=self.user,
            status='draft'
        )
        inv_sent = Invoice.objects.create(
            invoice_number='SENT-1',
            business=self.business,
            client_name='Sent Client',
            issue_date=today, due_date=today,
            subtotal=20, tax_rate=0, tax_amount=0, total_amount=20,
            created_by=self.user,
            status='sent'
        )

        # Case-insensitive status filter
        resp = client.get('/api/invoices/?status=Draft')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(resp.data['results'][0]['status'].lower(), 'draft')

        # Search by invoice number
        resp = client.get('/api/invoices/?search=SENT-1')
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(len(resp.data['results']), 1)
        found = any(r['invoice_number'] == 'SENT-1' for r in resp.data['results'])
        self.assertTrue(found)

    def test_invoice_create_requires_business(self):
        client = APIClient()
        client.force_authenticate(user=self.user)
        today = timezone.now().date()

        invoice_payload = {
            'business': '',
            'client_name': 'No Business Client',
            'issue_date': today,
            'due_date': today,
            'currency': 'NGN',
            'tax_rate': 0,
            'notes': 'Test invoice without business',
            'line_items': [
                {'description': 'Service', 'quantity': 1, 'unit_price': 100}
            ]
        }

        resp = client.post('/api/invoices/', invoice_payload, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('business', resp.data)
        self.assertEqual(resp.data['business'][0], 'Business id is required.')
