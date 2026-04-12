from .settings import *


DEBUG = False
AUTH_COOKIE_SECURE = False
ACTIVE_FILIAL_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / '.django_test.sqlite3',
    }
}

PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
}