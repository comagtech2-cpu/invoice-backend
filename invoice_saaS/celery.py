import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'invoice_saaS.settings')

app = Celery('invoice_saaS')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
