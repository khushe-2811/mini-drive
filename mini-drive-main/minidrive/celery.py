import os
from celery import Celery

# Set default Django settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "minidrive.settings")

app = Celery("minidrive")

# Use CELERY_ prefixed settings from Django settings
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()

# Configure as eager (no separate worker needed)
app.conf.task_always_eager = True
app.conf.task_eager_propagates = True
