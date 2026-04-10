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
    'localhost',
    '127.0.0.1',
    'codasite.com.ng',  # 👈 Add this once you buy your domain
]


# Application definition

INSTALLED_APPS = [
    'whitenoise.runserver_nostatic',
    # Cloudinary
    'cloudinary_storage',
    'django.contrib.staticfiles',
    'cloudinary',
    # Cloudinary
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',

    'django_htmx',
    # Tailwind down 👇🏻
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

# /////////////////////// --- STATIC FILES (CSS, JavaScript, Images) ---
# Static Files (CSS, JavaScript, Images)


# settings.py
# settings.py

# 📂 Media Files (User Uploads) go to Cloudinary
DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'

# 🎨 Static Files (CSS/JS) go to WhiteNoise
# Note: Use this exact string for WhiteNoise 6.0+
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# // --- STATIC FILES CONFIG ---
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

STATICFILES_DIRS = [
    BASE_DIR / 'static',
    BASE_DIR / 'theme' / 'static',  # 👈 This is where Tailwind puts the CSS
]

# WhiteNoise for efficient static file serving on Render

# Media Files (Uploaded Photos & Videos)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# // Custom acout

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

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

# 🚀 1. The Master Key
RESEND_API_KEY = os.getenv('RESEND_API_KEY')

# 📧 2. The Official "From" Address
DEFAULT_FROM_EMAIL = 'CodaSite Audit <reports@codasite.com.ng>'

# 🛑 3. Add this to prevent WinError 10061
# This tells Django: "Don't look for a local SMTP server; we are using the Resend SDK instead."
EMAIL_BACKEND = 'django.core.mail.backends.dummy.EmailBackend'

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
# /// Cound

# /// Tell Django where your custom login page is

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'index'
LOGOUT_REDIRECT_URL = 'login'
AUTH_USER_MODEL = 'account.User'
