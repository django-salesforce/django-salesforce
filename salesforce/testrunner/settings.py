# Django settings for testrunner project.
import os

DEBUG = True
TEMPLATE_DEBUG = DEBUG

ADMINS = (
	# ('Your Name', 'your_email@example.com'),
)

PERSON_ACCOUNT_ACTIVATED = False

DATABASES = {
	'default': {
		'ENGINE': 'django.db.backends.sqlite3',
		'NAME': 'salesforce_testrunner_db',
	},
	# The variable DATABASES should be redefined in local_settings with details
	# in order to protect private secret values from unintentional committing.
	'salesforce': {
		'ENGINE': 'salesforce.backend',
		"CONSUMER_KEY" : os.environ.get('SF_CONSUMER_KEY', ''),
		"CONSUMER_SECRET" : os.environ.get('SF_CONSUMER_SECRET', ''),
		'USER': os.environ.get('SF_USER', ''),
		'PASSWORD': os.environ.get('SF_PASSWORD', ''),
		'HOST': 'https://login.salesforce.com',
	}
}

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# On Unix systems, a value of None will cause Django to use the same
# timezone as the operating system.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'America/New_York'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale
USE_L10N = True

# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/home/media/media.lawrence.com/media/"
MEDIA_ROOT = ''

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
# Examples: "http://media.lawrence.com/media/", "http://example.com/media/"
MEDIA_URL = ''

# Absolute path to the directory static files should be collected to.
# Don't put anything in this directory yourself; store your static files
# in apps' "static/" subdirectories and in STATICFILES_DIRS.
# Example: "/home/media/media.lawrence.com/static/"
STATIC_ROOT = ''

# URL prefix for static files.
# Example: "http://media.lawrence.com/static/"
STATIC_URL = '/static/'

# Additional locations of static files
STATICFILES_DIRS = (
	# Put strings here, like "/home/html/static" or "C:/www/django/static".
	# Always use forward slashes, even on Windows.
	# Don't forget to use absolute paths, not relative paths.
)

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = (
	'django.contrib.staticfiles.finders.FileSystemFinder',
	'django.contrib.staticfiles.finders.AppDirectoriesFinder',
#	 'django.contrib.staticfiles.finders.DefaultStorageFinder',
)

# Make this unique, and don't share it with anybody.
SECRET_KEY = '6$y&o(28l)#o1_2rafojb_&zxi*jnivkv)ygj#!01kt0ypsxe$'

SITE_ID = 1

MIDDLEWARE_CLASSES = (
	'django.middleware.common.CommonMiddleware',
	'django.contrib.sessions.middleware.SessionMiddleware',
	'django.middleware.csrf.CsrfViewMiddleware',
	'django.contrib.auth.middleware.AuthenticationMiddleware',
	'django.contrib.messages.middleware.MessageMiddleware',
	'django.middleware.clickjacking.XFrameOptionsMiddleware',
)

ROOT_URLCONF = 'salesforce.testrunner.urls'

TEMPLATE_DIRS = (
	# Put strings here, like "/home/html/django_templates" or "C:/www/django/templates".
	# Always use forward slashes, even on Windows.
	# Don't forget to use absolute paths, not relative paths.
)

INSTALLED_APPS = (
	'django.contrib.auth',
	'django.contrib.contenttypes',
	'django.contrib.sessions',
	'django.contrib.sites',
	'django.contrib.messages',
	'django.contrib.staticfiles',
	'django.contrib.admin',
	'django.contrib.admindocs',
	'salesforce',
	'salesforce.testrunner.example',
)

SALESFORCE_DB_ALIAS = 'salesforce'
SALESFORCE_QUERY_TIMEOUT = 15
# Maximal number of retries after timeout.
#REQUESTS_MAX_RETRIES = 1
DATABASE_ROUTERS = [
	"salesforce.router.ModelRouter"
]

# A sample logging configuration. The only tangible logging
# performed by this configuration is to send an email to
# the site admins on every HTTP 500 error.
# See http://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.
LOGGING = {
	'version': 1,
	'disable_existing_loggers': False,
	'handlers': {
		"console": {
			"class": "logging.StreamHandler",
			"level": "DEBUG",
		},
		'mail_admins': {
			'level': 'ERROR',
			'class': 'django.utils.log.AdminEmailHandler',
			'filters': ['require_debug_false'],
		}
	},
	'loggers': {
		'django.request': {
			'handlers': ['mail_admins'],
			'level': 'ERROR',
			'propagate': True,
		},
		'salesforce': {
			'handlers': ['console'],
			'level': 'INFO',
			'propagate': True,
		},
		'salesforce.testrunner': {
			'handlers': ['console'],
			'level': 'INFO',
			'propagate': True,
		},
	},
	'filters': {
		'require_debug_false': {
			"()": "django.utils.log.RequireDebugFalse",
		}
	}
}

# Preventive workaround for some problems with IPv6 by restricting DNS queries
# in the Python process only to IPv4, until the support by SFDC become stable.
# SFDC enabled IPv6 for a week in March 2014. It caused long delays somewhere.
IPV4_ONLY = True

# Name of primary key - by default 'id'. The value 'Id' was the default for
# version "django-salesforce < 0.5".
#SF_PK = 'Id'

try:
	from salesforce.testrunner.local_settings import *
except ImportError:
	pass
