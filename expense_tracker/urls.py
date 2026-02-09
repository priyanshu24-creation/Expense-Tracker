from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth.views import LogoutView

from tracker.views import email_login, verify_otp


urlpatterns = [
    path('admin/', admin.site.urls),

    # auth (OTP login flow)
    path('login/', email_login, name='email_login'),
    path('verify/', verify_otp, name='verify_otp'),
    path('logout/', LogoutView.as_view(next_page='email_login'), name='logout'),

    # tracker app
    path('', include('tracker.urls')),
]

# media (profile images etc.)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
