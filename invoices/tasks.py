from celery import shared_task
from django.core.management import call_command

@shared_task
def send_due_reminders_task(rule_id=None):
    """Celery task wrapper to run reminder sending management command."""
    if rule_id:
        call_command('send_due_reminders', '--rule', str(rule_id))
    else:
        call_command('send_due_reminders')
