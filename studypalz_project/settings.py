from pathlib import Path
import os

# ------------------------------------------------------------------
# BASE & SECURITY
# ------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

# Retrieves the key from the environment variable set in the WSGI file
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')

# Fail fast if SECRET_KEY is missing
# if SECRET_KEY is None:
#     raise Exception("The DJANGO_SECRET_KEY environment variable is not set. Check your WSGI file!")

DEBUG = False

ALLOWED_HOSTS = ['studypalz3.pythonanywhere.com']


# ------------------------------------------------------------------
# APPLICATION DEFINITION
# ------------------------------------------------------------------

INSTALLED_APPS = [
    # Third-party apps
    'axes',             # django-axes for login protection

    'core',

    # Django contrib apps
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',

    'core.middleware.BotBlockerMiddleware',

    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',

    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'axes.middleware.AxesMiddleware',        # Axes middleware after auth

    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'studypalz_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': ["templates"],
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

WSGI_APPLICATION = 'studypalz_project.wsgi.application'


# ------------------------------------------------------------------
# DATABASE
# ------------------------------------------------------------------

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# ------------------------------------------------------------------
# AUTH / PASSWORDS
# ------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Use Axes + default Django auth backend
AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesBackend',                 # Axes first
    'django.contrib.auth.backends.ModelBackend', # then normal Django auth
]

LOGIN_REDIRECT_URL = 'dashboard'


# ------------------------------------------------------------------
# INTERNATIONALIZATION
# ------------------------------------------------------------------

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Asia/Kolkata'

USE_I18N = True

USE_TZ = True


# ------------------------------------------------------------------
# STATIC FILES

# ------------------------------------------------------------------
# STATIC FILES
# ------------------------------------------------------------------
STATIC_URL = 'static/'

# The directory where collectstatic will gather all static files for production
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Where your app-level static files live (e.g. core/static/)
STATICFILES_DIRS = [
 BASE_DIR / 'core' / 'static',
]

# ------------------------------------------------------------------
# DEFAULT PRIMARY KEY
# ------------------------------------------------------------------

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# ------------------------------------------------------------------
# SECURITY (HTTPS / COOKIES / HSTS)
# ------------------------------------------------------------------

SECURE_SSL_REDIRECT = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True

# HSTS Configuration
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True


# ------------------------------------------------------------------
# CUSTOM SETTINGS
# ------------------------------------------------------------------

# Block specific IPs (used by your BotBlockerMiddleware)
BLOCKED_IPS = [
    '140.248.8.19',
    '103.81.39.68',
    '172.225.137.212',
    '104.28.37.76',
    '172.225.137.213',
    '172.225.201.21',
    # Add any other malicious IPs here
]


# ------------------------------------------------------------------
# DJANGO-AXES SETTINGS
# ------------------------------------------------------------------

AXES_ENABLED = True
AXES_FAILURE_LIMIT = 5          # lock after 5 failed attempts
AXES_COOLOFF_TIME = 1           # in hours (1 hour lockout)
AXES_LOCK_OUT_AT_FAILURE = True

ALLOWED_COUNTRY = 'India'
ALLOWED_REGION = 'Maharashtra'   # state
ALLOWED_CITY = 'Pune'

# If you later create a custom lockout page template:
AXES_LOCKOUT_TEMPLATE = 'core/lockout.html'
LOGIN_URL = 'login/'