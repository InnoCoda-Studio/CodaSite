import os
from pathlib import Path
import dj_database_url
from dotenv import load_dotenv

# Cloudinary
import cloudinary.uploader
from cloudinary.utils import cloudinary_url

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# 1. Load the .env file explicitly using the BASE_DIR path
load_dotenv(os.path.join(BASE_DIR, '.env'))

# Quick-start development settings - unsuitable for production
# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY')

# 2. The Dynamic Debug Toggle
# This reads from your .env locally (True), but defaults to False on Render
DEBUG = os.getenv('DEBUG', 'False') == 'True'

# settings.py

# 🟢 Only allow your official Render URL and your future domain
ALLOWED_HOSTS = [
    'codasite-6xbb.onrender.com',
    'codasite.com.ng',
    'www.codasite.com.ng',
    'localhost',
    '127.0.0.1',
    '127.0.0.2',
]


# Application definition

INSTALLED_APPS = [
    'whitenoise.runserver_nostatic',
    # Cloudinary
    'django.contrib.staticfiles',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    # Cloudinary
    'cloudinary_storage',
    'cloudinary',
    # Tailwind down 👇🏻
    'django_htmx',
    'tailwind',

    'theme',
    # 'django_browser_reload',
    # tailwin up ☝🏻
    "account",
    "site_management",
    'anymail',
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
    'django_htmx.middleware.HtmxMiddleware',

    # 🛑 YOUR NEW CODASITE BOUNCER 🛑
    'site_management.middleware.SubscriptionEnforcementMiddleware',
]

ROOT_URLCONF = 'codasite.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / "templates"],

        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',

                # 🎯 YOUR NEW CONTEXT PROCESSOR (The Live Ops Anchor)
                'site_management.context_processors.active_site_processor',


            ],
        },
    },
]
WSGI_APPLICATION = 'codasite.wsgi.application'


# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

# "SQLITE"
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.sqlite3',
#         'NAME': BASE_DIR / 'db.sqlite3',
#     }
# }

"Superbase Database"
DATABASES = {
    'default': dj_database_url.config(
        default=os.getenv('DATABASE_URL')
    )
}








# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

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


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

# settings.py

LANGUAGE_CODE = 'en-us'

# 🌍 ONLY ONE TIME_ZONE DEFINITION
TIME_ZONE = 'Africa/Lagos'

USE_I18N = True

# 🛰️ SET THIS TO TRUE
USE_TZ = True


# // Static files (CSS, JavaScript, Images)
# // https://docs.djangoproject.com/en/6.0/howto/static-files/

# settings.py

# STORAGES = {
#     "default": {
#         "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage",
#     },
#     "staticfiles": {
#         # 🛡️ Uses cache-busting hashing so styles never look broken or cached
#         "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
#     },
# }


STORAGES = {
    "default": {
        "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
# 🏁 Match the legacy setting as well

# 2. Paths Configuration
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

STATICFILES_DIRS = [
    BASE_DIR / 'static',
    BASE_DIR / 'theme' / 'static',
]

# 3. Media Files (User Uploads)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'



# ADD THIS TEMPORARY FIX
STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
]
# //////////////////////////
# // Tailwind 👇🏻
TAILWIND_APP_NAME = 'theme'

INTERNAL_IPS = [
    "127.0.0.1",
]
# /// Tailwind ☝🏻
# //////////////////////////


# ////////// Cloudinary Config using .env
CLOUDINARY_STORAGE = {
    'CLOUD_NAME': os.getenv('CLOUDINARY_CLOUD_NAME'),
    'API_KEY': os.getenv('CLOUDINARY_API_KEY'),
    'API_SECRET': os.getenv('CLOUDINARY_API_SECRET'),
    'SECURE': True,  # 🟢 This forces HTTPS for all images
}


# 🚀 THE CONSOLIDATED PRODUCTION SECURITY COMMAND CENTER
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    # Use SECURE_SSL_REDIRECT = True only if you are sure your domain is fully configured.
    # For now, let's turn it OFF to see if the 500 errors stop.
    SECURE_SSL_REDIRECT = False 
    
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
else:
    # Settings for LOCALHOST (Development)
    # This stops the "Bad Request" and HTTPS errors locally
    SECURE_SSL_REDIRECT = False
    SECURE_HSTS_SECONDS = 0
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
# /// Cound

# /// Tell Django where your custom login page is
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'index'
LOGOUT_REDIRECT_URL = 'login'
AUTH_USER_MODEL = 'account.User'

# STATICFILES_STORAGE = 'whitenoise.storage.StaticFilesStorage'
# WHITENOISE_KEEP_ONLY_HASHED_FILES = True

# --- EMAIL SETTINGS (Anymail / Resend API) ---

# 1. Fetch the key from your .env file or Render dashboard
RESEND_API_KEY = os.getenv('RESEND_API_KEY')

# 2. Tell Django to use Anymail (bypasses Render's SMTP block)
EMAIL_BACKEND = "anymail.backends.resend.EmailBackend"

# 3. Pass the key to Anymail
ANYMAIL = {
    "RESEND_API_KEY": RESEND_API_KEY,
}

# 4. Default sender for password resets and system emails
DEFAULT_FROM_EMAIL = 'CodaSite Audit <reports@codasite.com.ng>'

# Tell Django it's sitting behind a secure proxy (Render)
# SECURITY SETTINGS FOR RENDER
# SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
# SESSION_COOKIE_SECURE = True
# CSRF_COOKIE_SECURE = True
# # Force Cloudinary to always use HTTPS
# SECURE_SSL_REDIRECT = True

# Paystack Configuration
PAYSTACK_SECRET_KEY = os.environ.get('PAYSTACK_SECRET_KEY')
PAYSTACK_PUBLIC_KEY = os.environ.get('PAYSTACK_PUBLIC_KEY')


try:
    from .settings_local import *
except ImportError:
    pass




# Force Django to log to stdout so Render captures it in the logs
import sys
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'stream': sys.stdout,
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING', # Change to 'DEBUG' if you still can't see it
    },
}