import os
import django
from mangum import Mangum

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "expense_tracker.settings")
django.setup()

from expense_tracker.wsgi import application

handler = Mangum(application)
