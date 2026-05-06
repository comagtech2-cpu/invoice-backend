from django.core.management.base import BaseCommand
from django.utils import timezone
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from invoices.models import ReminderRule

class Command(BaseCommand):
    help = 'Send due invoice reminders based on ReminderRule'

    def add_arguments(self, parser):
        parser.add_argument('--rule', type=int, help='Specific ReminderRule id to run')

    def handle(self, *args, **options):
        today = timezone.now().date()
        rule_id = options.get('rule')
        queryset = ReminderRule.objects.filter(active=True)
        if rule_id:
            queryset = queryset.filter(id=rule_id)

        sent = 0
        for rule in queryset:
            invoices = rule.get_target_invoices()
            for invoice in invoices:
                try:
                    subject = rule.subject_template or f'Reminder: Invoice {invoice.invoice_number} due on {invoice.due_date}'
                    context = {
                        'invoice': invoice,
                        'business': invoice.business,
                        'client_name': invoice.client_name,
                        'due_date': invoice.due_date,
                        'total_amount': invoice.total_amount,
                    }
                    text_content = rule.text_template or render_to_string('emails/invoice_reminder.txt', context)
                    try:
                        html_content = render_to_string('emails/invoice_reminder.html', context)
                    except Exception:
                        # Fall back to standard invoice notification templates if reminder templates don't exist
                        try:
                            html_content = render_to_string('emails/invoice_notification.html', context)
                        except Exception:
                            html_content = None

                    msg = EmailMultiAlternatives(subject, text_content, settings.DEFAULT_FROM_EMAIL, [invoice.client_email])
                    if html_content:
                        msg.attach_alternative(html_content, 'text/html')

                    # Attach PDF if available
                    try:
                        from invoices.utils import generate_invoice_pdf
                        pdf_buffer = generate_invoice_pdf(invoice.id)
                        if pdf_buffer:
                            msg.attach(f'invoice_{invoice.invoice_number}.pdf', pdf_buffer, 'application/pdf')
                    except Exception:
                        # Non-fatal - proceed without attachment
                        pass

                    msg.send()
                    sent += 1
                except Exception as e:
                    self.stderr.write(f"Failed to send reminder for invoice {invoice.id}: {str(e)}")

            rule.last_sent = timezone.now()
            rule.save()

        self.stdout.write(self.style.SUCCESS(f'Sent {sent} reminders'))
