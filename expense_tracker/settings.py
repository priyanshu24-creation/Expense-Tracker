"""
Django settings for expense_tracker project.
"""

from pathlib import Path
import os
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent


# ======================
# SECURITY
# ======================

SECRET_KEY = os.environ.get("SECRET_KEY")

DEBUG = False

ALLOWED_HOSTS = ['.onrender.com', 'localhost']

CSRF_TRUSTED_ORIGINS = ['https://*.onrender.com']


# ======================
# APPLICATIONS
# ======================

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'tracker',
]


MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


ROOT_URLCONF = 'expense_tracker.urls'


TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],   # using app templates
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]


WSGI_APPLICATION = 'expense_tracker.wsgi.application'


# ======================
# DATABASE (PostgreSQL)
# ======================

DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get("DATABASE_URL"),
        conn_max_age=600,
        ssl_require=True
    )
}


# ======================
# PASSWORD VALIDATION
# ======================

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# ======================
# INTERNATIONALIZATION
# ======================

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


# ======================
# STATIC FILES
# ======================

STATIC_URL = '/static/'

STATICFILES_DIRS = [
    BASE_DIR / "tracker/static"
]

STATIC_ROOT = BASE_DIR / "staticfiles"

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'


# ======================
# MEDIA FILES
# ======================

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# ======================
# AUTH REDIRECTS
# ======================

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'


# ======================
# DEFAULT PRIMARY KEY
# ======================

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
