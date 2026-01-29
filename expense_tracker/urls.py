from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from tracker.views import email_login, verify_otp

urlpatterns = [
    path('admin/', admin.site.urls),

    # OTP login system
    path('login/', email_login, name='email_login'),
    path('verify/', verify_otp, name='verify_otp'),
    path('logout/', include('django.contrib.auth.urls')),  # keeps logout

    # app routes
    path('', include('tracker.urls')),

    # password change (optional)
    path('password-change/', include('django.contrib.auth.urls')),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
