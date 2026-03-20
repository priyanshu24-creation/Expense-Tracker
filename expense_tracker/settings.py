from pathlib import Path
import os
from dotenv import load_dotenv
import dj_database_url
from django.core.exceptions import ImproperlyConfigured

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# ======================
# SECURITY
# ======================

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")

DEBUG = os.getenv("DEBUG", "True") == "True"

RAW_CLOUDINARY_URL = (os.getenv("CLOUDINARY_URL") or "").strip().strip("'").strip('"')
CLOUDINARY_URL_HAS_PLACEHOLDER = any(
    token in RAW_CLOUDINARY_URL
    for token in ("<", ">", "your_api_key", "your_api_secret")
)
USE_CLOUDINARY = bool(RAW_CLOUDINARY_URL) and not CLOUDINARY_URL_HAS_PLACEHOLDER

ALLOWED_HOSTS = [
    ".onrender.com",
    "localhost",
    "127.0.0.1",
]

CSRF_TRUSTED_ORIGINS = [
    "https://*.onrender.com"
]

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ======================
# APPS
# ======================

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "tracker",
]

if USE_CLOUDINARY:
    INSTALLED_APPS += [
        "cloudinary_storage",
        "cloudinary",
    ]

# ======================
# MIDDLEWARE
# ======================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# ======================
# URLS / TEMPLATES
# ======================

ROOT_URLCONF = "expense_tracker.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "expense_tracker.wsgi.application"

# ======================
# DATABASE
# ======================

DATABASE_URL = os.getenv("DATABASE_URL")
USE_REMOTE_DB = os.getenv("USE_REMOTE_DB", "False") == "True"

if DATABASE_URL and (not DEBUG or USE_REMOTE_DB):
    remote_database = dj_database_url.parse(
        DATABASE_URL,
        conn_max_age=int(os.getenv("DB_CONN_MAX_AGE", "600")),
        ssl_require=True,
    )
    remote_database["CONN_HEALTH_CHECKS"] = True
    remote_database.setdefault("OPTIONS", {})
    remote_database["OPTIONS"].setdefault(
        "connect_timeout",
        int(os.getenv("DB_CONNECT_TIMEOUT", "10")),
    )
    DATABASES = {
        "default": remote_database
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

if not DEBUG and not DATABASE_URL:
    raise ImproperlyConfigured(
        "DATABASE_URL must be set when DEBUG=False to avoid data loss in production."
    )

if not DEBUG and SECRET_KEY == "dev-secret-key":
    raise ImproperlyConfigured(
        "SECRET_KEY must be set to a secure value when DEBUG=False."
    )

# ======================
# PASSWORD VALIDATION
# ======================

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ======================
# INTERNATIONALIZATION
# ======================

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ======================
# LOGIN REDIRECTS
# ======================

LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"

# ======================
# STATIC FILES
# ======================

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

STATICFILES_DIRS = []
tracker_static = BASE_DIR / "tracker" / "static"
if tracker_static.exists():
    STATICFILES_DIRS.append(tracker_static)

STATICFILES_STORAGE = "whitenoise.storage.CompressedStaticFilesStorage"

# ======================
# MEDIA FILES
# ======================

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_FILE_STORAGE = (
    "cloudinary_storage.storage.MediaCloudinaryStorage"
    if USE_CLOUDINARY
    else "django.core.files.storage.FileSystemStorage"
)

STORAGES = {
    "default": {"BACKEND": DEFAULT_FILE_STORAGE},
    "staticfiles": {"BACKEND": STATICFILES_STORAGE},
}

if USE_CLOUDINARY:
    CLOUDINARY_STORAGE = {
        "CLOUDINARY_URL": RAW_CLOUDINARY_URL,
    }

# ======================
# SENDGRID EMAIL CONFIG
# ======================

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY") or os.getenv("SENDERGRID_API_KEY")
DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL",
    "trackexpenseteam@gmail.com"
)

# ======================
# DJANGO EMAIL BACKEND
# ======================

EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.sendgrid.net")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "apikey")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", SENDGRID_API_KEY or "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True") == "True"
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "10"))

# ======================
# GMAIL SMTP (DEV/ALT)
# ======================

USE_GMAIL_SMTP = os.getenv("USE_GMAIL_SMTP", "False") == "True"
# Avoid SMTP in production (most PaaS block outbound SMTP ports).
if not DEBUG:
    USE_GMAIL_SMTP = False
if USE_GMAIL_SMTP:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = "smtp.gmail.com"
    EMAIL_PORT = 587
    EMAIL_USE_TLS = True
    EMAIL_HOST_USER = os.getenv("GMAIL_USER") or DEFAULT_FROM_EMAIL
    EMAIL_HOST_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
    if EMAIL_HOST_USER:
        DEFAULT_FROM_EMAIL = EMAIL_HOST_USER

# ======================
# PREDICTION THRESHOLDS
# ======================

PREDICTION_OVR_PROJ_THRESHOLD = float(os.getenv("PREDICTION_OVR_PROJ_THRESHOLD", "0.15"))
PREDICTION_OVR_PACE_THRESHOLD = float(os.getenv("PREDICTION_OVR_PACE_THRESHOLD", "0.20"))
PREDICTION_UNDER_THRESHOLD = float(os.getenv("PREDICTION_UNDER_THRESHOLD", "0.60"))
PREDICTION_STABLE_THRESHOLD = float(os.getenv("PREDICTION_STABLE_THRESHOLD", "0.10"))
PREDICTION_FIRST_WEEK_DAYS = int(os.getenv("PREDICTION_FIRST_WEEK_DAYS", "7"))

# ======================
# DEFAULT PK
# ======================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ======================
# LOGGING
# ======================

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "ignore_broken_pipe": {
            "()": "expense_tracker.logging_filters.IgnoreBrokenPipeFilter",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "filters": ["ignore_broken_pipe"],
        },
    },
    "loggers": {
        "django.server": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
