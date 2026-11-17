import os
from datetime import timedelta
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
STAGING_PUBLICATION_HOSTS=tuple(h.strip().lower() for h in os.environ.get('STAGING_PUBLICATION_HOSTS','').split(',') if h.strip())
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', '')
if len(SECRET_KEY) < 32:
    raise ImproperlyConfigured('Set DJANGO_SECRET_KEY to a random value of at least 32 characters.')
DEBUG = os.environ.get('DJANGO_DEBUG', 'false').lower() == 'true'
ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1,testserver').split(',')
INSTALLED_APPS = [
    'django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes',
    'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles',
    'rest_framework', 'drf_spectacular', 'axes', 'platform_core',
]
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware', 'platform_core.middleware.RequestIDMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware', 'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware', 'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware', 'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'axes.middleware.AxesMiddleware',
]
ROOT_URLCONF = 'config.urls'
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates',
              'DIRS': [BASE_DIR / 'templates'], 'APP_DIRS': True,
              'OPTIONS': {'context_processors': [
                  'django.template.context_processors.request', 'django.contrib.auth.context_processors.auth',
                  'django.contrib.messages.context_processors.messages',
                  'platform_core.context.product_access',
              ]}}]
WSGI_APPLICATION = 'config.wsgi.application'
DATABASES = {'default': {
    'ENGINE': 'django.db.backends.postgresql', 'NAME': os.environ.get('POSTGRES_DB', 'seo'),
    'USER': os.environ.get('POSTGRES_USER', 'seo'), 'PASSWORD': os.environ.get('POSTGRES_PASSWORD', ''),
    'HOST': os.environ.get('POSTGRES_HOST', 'db'), 'PORT': os.environ.get('POSTGRES_PORT', '5432'),
    'CONN_MAX_AGE': 60, 'OPTIONS': {'connect_timeout': 5},
}}
AUTH_USER_MODEL = 'platform_core.User'
AUTHENTICATION_BACKENDS = ['axes.backends.AxesStandaloneBackend', 'django.contrib.auth.backends.ModelBackend']
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 12}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Colombo'
USE_I18N = True
USE_TZ = True
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
MEDIA_ROOT = Path(os.environ.get('UPLOAD_ROOT', '/data/uploads'))
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = LOGIN_URL
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = 28800
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
# Keep an origin referrer for CSRF validation without disclosing invitation URL paths.
SECURE_REFERRER_POLICY = 'strict-origin'
SECURE_SSL_REDIRECT = not DEBUG
X_FRAME_OPTIONS = 'DENY'
PASSWORD_RESET_TIMEOUT = 3600
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(minutes=15)
AXES_LOCKOUT_PARAMETERS = [['username', 'ip_address']]
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_TEMPLATE = 'registration/locked.html'
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ['rest_framework.authentication.SessionAuthentication'],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination', 'PAGE_SIZE': 25,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_RENDERER_CLASSES': ['rest_framework.renderers.JSONRenderer'],
}
SPECTACULAR_SETTINGS = {'TITLE': 'SEO Platform API', 'VERSION': '1.0.0', 'SERVE_INCLUDE_SCHEMA': False}
CELERY_BROKER_URL = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
CELERY_TASK_IGNORE_RESULT = True
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_TIME_LIMIT = 300
CELERY_TASK_SOFT_TIME_LIMIT = 270
CELERY_IMPORTS = ('platform_core.publish_tasks','platform_core.research','platform_core.draft_assistant','platform_core.metadata_cache','platform_core.search_metrics')
CELERY_BROKER_CONNECTION_TIMEOUT = 3
CONNECTION_ENCRYPTION_KEYS = [key for key in os.environ.get('CONNECTION_ENCRYPTION_KEYS', '').split(',') if key]
# A single fixed local fixture hostname; never user-controlled or enabled in production.
CONNECTOR_LOCAL_FIXTURE_ENABLED = DEBUG and os.environ.get('CONNECTOR_LOCAL_FIXTURE_ENABLED', 'false').lower() == 'true'
LOCAL_PUBLICATION_ENABLED = DEBUG and os.environ.get('LOCAL_PUBLICATION_ENABLED', 'false').lower() == 'true'
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY','')
GOOGLE_OAUTH_CLIENT_ID=os.environ.get('GOOGLE_OAUTH_CLIENT_ID','')
GOOGLE_OAUTH_CLIENT_SECRET=os.environ.get('GOOGLE_OAUTH_CLIENT_SECRET','')
GOOGLE_OAUTH_REDIRECT_URI=os.environ.get('GOOGLE_OAUTH_REDIRECT_URI','http://localhost:8000/integrations/google/callback/')
LOGGING={'version':1,'disable_existing_loggers':False,
    'filters':{'oauth_redact':{'()':'platform_core.log_filters.CallbackLogFilter'}},
    'formatters':{'server':{'()':'django.utils.log.ServerFormatter','format':'[{server_time}] {message}','style':'{'}},
    'handlers':{'redacted_server':{'class':'logging.StreamHandler','formatter':'server','filters':['oauth_redact']}},
    'loggers':{'django.server':{'handlers':['redacted_server'],'level':'INFO','propagate':False}}}
GEMINI_MODEL = os.environ.get('GEMINI_MODEL','')
RESEARCH_AI_ENABLED = os.environ.get('RESEARCH_AI_ENABLED','false').lower() == 'true'
PROTECTED_STAGING_HOSTS = [host.strip().lower() for host in os.environ.get('PROTECTED_STAGING_HOSTS','').split(',') if host.strip()]
PROTECTED_STAGING_ORIGINS = {}
if os.environ.get('DENIM_STAGING_ORIGIN_IP',''):
    PROTECTED_STAGING_ORIGINS['staging.denimyard.com'] = {
        'address':os.environ['DENIM_STAGING_ORIGIN_IP'],
        'ca_file':str(BASE_DIR/'platform_core/certificates/denim_staging_ca.pem'),
    }
