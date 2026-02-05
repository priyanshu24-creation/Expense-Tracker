"""
ASGI config for expense_tracker project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/
"""

import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_tracker.settings')

application = get_asgi_application()
