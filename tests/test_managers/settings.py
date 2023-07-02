from django.utils.crypto import get_random_string
from salesforce.testrunner.settings import DATABASES, DJSF_LICENSE_KEY  # noqa # necessary for setup

SECRET_KEY = get_random_string(length=32)

INSTALLED_APPS = ['salesforce', 'tests.test_managers']
DATABASE_ROUTERS = ["salesforce.router.ModelRouter"]
SF_LAZY_CONNECT = True
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'  # not important for Salesforce, but for Django warnings
