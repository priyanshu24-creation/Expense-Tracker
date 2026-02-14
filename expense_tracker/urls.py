from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.views.static import serve as static_serve
from django.contrib.auth.views import LogoutView
from django.views.generic import TemplateView
import os
import sys
import re

from tracker.views import email_login, email_signup, verify_otp


urlpatterns = [
    path('admin/', admin.site.urls),

    # auth (OTP login flow)
    path('login/', email_login, name='email_login'),
    path('signup/', email_signup, name='email_signup'),
    path('verify/', verify_otp, name='verify_otp'),
    path('logout/', LogoutView.as_view(next_page='email_login'), name='logout'),

    # tracker app
    path('', include('tracker.urls')),

    # PWA assets
    path("manifest.json", TemplateView.as_view(
        template_name="manifest.json",
        content_type="application/json"
    )),
    path("service-worker.js", TemplateView.as_view(
        template_name="service-worker.js",
        content_type="application/javascript"
    )),
]

# media (profile images etc.)
serve_media = (
    settings.DEBUG
    or os.getenv("SERVE_MEDIA", "False") == "True"
    or "runserver" in sys.argv
    or not getattr(settings, "USE_CLOUDINARY", False)
)
if serve_media:
    media_prefix = re.escape(settings.MEDIA_URL.lstrip("/"))
    urlpatterns += [
        re_path(rf"^{media_prefix}(?P<path>.*)$", static_serve, {"document_root": settings.MEDIA_ROOT}),
    ]
