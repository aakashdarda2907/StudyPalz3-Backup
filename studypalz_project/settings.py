from pathlib import Path
import os
from dotenv import load_dotenv


# ------------------------------------------------------------------
# BASE DIRECTORY & ENVIRONMENT
# ------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

# Explicitly load .env from the project root
load_dotenv(BASE_DIR / ".env")


# ------------------------------------------------------------------
# SECURITY
# ------------------------------------------------------------------

SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]

DEBUG = False

ALLOWED_HOSTS = [
    "studypalz3.pythonanywhere.com",
]


# ------------------------------------------------------------------
# RAZORPAY
# ------------------------------------------------------------------

RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET")
RAZORPAY_WEBHOOK_SECRET = os.environ.get("RAZORPAY_WEBHOOK_SECRET")


# ------------------------------------------------------------------
# APPLICATION DEFINITION
# ------------------------------------------------------------------

INSTALLED_APPS = [
    # Third-party apps
    "axes",

    # Local apps
    "core",

    # Django contrib apps
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]


MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",

    "core.middleware.BotBlockerMiddleware",

    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",

    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "axes.middleware.AxesMiddleware",

    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


ROOT_URLCONF = "studypalz_project.urls"


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


WSGI_APPLICATION = "studypalz_project.wsgi.application"


# ------------------------------------------------------------------
# DATABASE
# ------------------------------------------------------------------

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}


# ------------------------------------------------------------------
# PASSWORD VALIDATION
# ------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "MinimumLengthValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "CommonPasswordValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "NumericPasswordValidator"
        ),
    },
]


# ------------------------------------------------------------------
# AUTHENTICATION
# ------------------------------------------------------------------

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesBackend",
    "django.contrib.auth.backends.ModelBackend",
]

LOGIN_REDIRECT_URL = "dashboard"

LOGIN_URL = "open_signup/"


# ------------------------------------------------------------------
# INTERNATIONALIZATION
# ------------------------------------------------------------------

LANGUAGE_CODE = "en-us"

TIME_ZONE = "Asia/Kolkata"

USE_I18N = True

USE_TZ = True


# ------------------------------------------------------------------
# STATIC FILES
# ------------------------------------------------------------------

STATIC_URL = "static/"

STATIC_ROOT = BASE_DIR / "staticfiles"

STATICFILES_DIRS = [
    BASE_DIR / "core" / "static",
]


# ------------------------------------------------------------------
# DEFAULT PRIMARY KEY
# ------------------------------------------------------------------

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ------------------------------------------------------------------
# HTTPS / SECURITY / COOKIES
# ------------------------------------------------------------------

SECURE_SSL_REDIRECT = True

CSRF_COOKIE_SECURE = True

SESSION_COOKIE_SECURE = True


# ------------------------------------------------------------------
# HSTS
# ------------------------------------------------------------------

SECURE_HSTS_SECONDS = 31536000  # 1 year

SECURE_HSTS_INCLUDE_SUBDOMAINS = True

SECURE_HSTS_PRELOAD = True


# ------------------------------------------------------------------
# CUSTOM BOT / IP BLOCKING
# ------------------------------------------------------------------

BLOCKED_IPS = [
    "140.248.8.19",
    "103.81.39.68",
    "172.225.137.212",
    "104.28.37.76",
    "172.225.137.213",
    "172.225.201.21",
]


# ------------------------------------------------------------------
# DJANGO-AXES
# ------------------------------------------------------------------

AXES_ENABLED = True

AXES_FAILURE_LIMIT = 5

AXES_COOLOFF_TIME = 1

AXES_LOCK_OUT_AT_FAILURE = True

AXES_LOCKOUT_TEMPLATE = "core/lockout.html"


# ------------------------------------------------------------------
# LOCATION SETTINGS
# ------------------------------------------------------------------

ALLOWED_COUNTRY = "India"

ALLOWED_REGION = "Maharashtra"

ALLOWED_CITY = "Pune"
