from django.utils.crypto import get_random_string
from salesforce.testrunner.settings import DATABASES, DJSF_LICENSE_KEY  # noqa

# DATABASES = {'default': DATABASES['salesforce']}
SECRET_KEY = get_random_string(length=32)
# SALESFORCE_DB_ALIAS = 'default'
# ROOT_URLCONF = None
INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # 'django.contrib.admin',
    # 'django.contrib.admindocs',
    'salesforce',
    # 'django.contrib.contenttypes',
    'tests.test_mock2',
]
DATABASE_ROUTERS = ["salesforce.router.ModelRouter"]
SF_LAZY_CONNECT = True
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'  # not important for Salesforce, but for Django warnings
