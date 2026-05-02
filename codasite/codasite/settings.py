import os  # Make sure this is at the top of settings.py
from pathlib import Path
import os
import dj_database_url
from dotenv import load_dotenv
# Cloudinary
import cloudinary
import cloudinary.uploader
from cloudinary.utils import cloudinary_url

load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(os.path.join(BASE_DIR, '.env'))
# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', 'False') == 'True'

# settings.py

# 🟢 Only allow your official Render URL and your future domain
ALLOWED_HOSTS = [
    'codasite.onrender.com',
    'codasite.com.ng',
    'www.codasite.com.ng',
    'localhost',
    '127.0.0.1',

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

STORAGES = {
    "default": {
        "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage",
    },
    "staticfiles": {
        # 🛡️ Switch to this - it's the most stable for Windows/Python 3.14
        "BACKEND": "whitenoise.storage.StaticFilesStorage",
    },
}

# 🏁 Match the legacy setting as well

# 2. Paths Configuration
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

STATICFILES_DIRS = [
    BASE_DIR / 'static',
    BASE_DIR / 'theme' / 'static',
]

# 3. Media Files (User Uploads)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# Add the path to your tailwind theme static folder


# --- 📧 INNOCODA EMAIL CONFIGURATION (RESEND) ---

# // password reset email
# // settings.py - INNOCODA EMAIL CONFIGURATION

# // --- InnoCoda Email Settings ---

# settings.py

# //////////////////////

# 📧 FORCED RESEND SETTINGS (No .env for now)

# /////////////////////////////////////////////////

# settings.py

# 🚀 1. The Master Key (Pulls from your Render Env or .env file)
# settings.py

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
# 🚀 SECURITY GUARDS (Only active in Production)
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000  # 🚨 This forces HTTPS permanently. Keep it here!
else:
    SECURE_SSL_REDIRECT = False

# This explicit config fixes the "Must supply cloud_name" error

# /// Cound

# /// Tell Django where your custom login page is

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'index'
LOGOUT_REDIRECT_URL = 'login'
AUTH_USER_MODEL = 'account.User'

STATICFILES_STORAGE = 'whitenoise.storage.StaticFilesStorage'
WHITENOISE_KEEP_ONLY_HASHED_FILES = True


# 🛑 3. Add this to prevent WinError 10061
# This tells Django: "Don't look for a local SMTP server; we are using the Resend SDK instead."


# RESEND_API_KEY = os.getenv('RESEND_API_KEY')
# DEFAULT_FROM_EMAIL = 'CodaSite Audit <reports@codasite.com.ng>'
# EMAIL_BACKEND = 'django.core.mail.backends.dummy.EmailBackend'
# EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
# settings.py

# 1. Use the SMTP backend (standard for most email services)
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.resend.com'
EMAIL_PORT = 465
EMAIL_USE_SSL = True
EMAIL_HOST_USER = 'resend'
EMAIL_HOST_PASSWORD = os.getenv('RESEND_API_KEY')
DEFAULT_FROM_EMAIL = 'CodaSite Audit <reports@codasite.com.ng>'

# 2


# settings.py

# EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
# EMAIL_HOST = 'smtp.resend.com'
# EMAIL_PORT = 587             # Use 587 instead of 465
# EMAIL_USE_TLS = True         # Use TLS instead of SSL
# EMAIL_USE_SSL = False        # Ensure this is False
# EMAIL_HOST_USER = 'resend'
# EMAIL_HOST_PASSWORD = os.getenv('RESEND_API_KEY')
# DEFAULT_FROM_EMAIL = 'CodaSite Audit <reports@codasite.com.ng>'


# # settings.py
# EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
# EMAIL_HOST = 'smtp.resend.com'
# EMAIL_PORT = 587             # Use 587 instead of 465
# EMAIL_USE_TLS = True         # Use TLS instead of SSL
# EMAIL_USE_SSL = False
# EMAIL_HOST_USER = 'resend'
# EMAIL_HOST_PASSWORD = os.getenv('RESEND_API_KEY')
# DEFAULT_FROM_EMAIL = 'CodaSite Audit <reports@codasite.com.ng>'