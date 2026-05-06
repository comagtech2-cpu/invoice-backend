from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from datetime import timedelta
from invoices.models import RecurringInvoice
from invoices.serializers import InvoiceSerializer

class Command(BaseCommand):
    help = 'Generate invoices for due recurring invoices'

    def add_arguments(self, parser):
        parser.add_argument('--id', type=str, help='Specific RecurringInvoice id to run')

    def handle(self, *args, **options):
        today = timezone.now().date()
        ri_id = options.get('id')
        queryset = RecurringInvoice.objects.filter(active=True)
        if ri_id:
            queryset = queryset.filter(id=ri_id)

        due = queryset.filter(next_run_date__lte=today)

        created_count = 0
        for ri in due:
            try:
                data = {}
                data['business'] = ri.business.id
                data['client_name'] = ri.client.name
                data['client_email'] = ri.client.email
                data['client_address'] = ri.client.address
                data['client_phone'] = ri.client.phone
                # template may contain line_items and other defaults
                template = ri.template or {}
                data['line_items'] = template.get('line_items', [])
                data['tax_rate'] = template.get('tax_rate', 0)
                data['currency'] = template.get('currency', 'USD')
                data['issue_date'] = today
                # default due in 30 days; can be overridden in template with 'due_days'
                due_days = template.get('due_days', 30)
                data['due_date'] = today + timedelta(days=due_days)
                data['notes'] = template.get('notes', '')

                serializer = InvoiceSerializer(data=data)
                if serializer.is_valid():
                    serializer.save(created_by=ri.created_by)
                    created_count += 1
                    ri.last_generated_at = timezone.now()
                    ri.next_run_date = ri.schedule_next_run()
                    # if end_date passed, deactivate
                    if ri.end_date and ri.next_run_date and ri.next_run_date > ri.end_date:
                        ri.active = False
                    ri.save()
                else:
                    self.stderr.write(f"Skipping RecurringInvoice {ri.id}: serializer errors {serializer.errors}")
            except Exception as e:
                self.stderr.write(f"Error generating for RecurringInvoice {ri.id}: {str(e)}")
        self.stdout.write(self.style.SUCCESS(f'Generated {created_count} invoices'))
