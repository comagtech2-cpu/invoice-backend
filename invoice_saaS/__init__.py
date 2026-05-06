try:
    from .celery import app as celery_app
except Exception:
    # Celery is optional for local development/testing where it may not be installed
    celery_app = None

__all__ = ('celery_app',)
