from django.utils.crypto import get_random_string
from salesforce.testrunner.settings import DATABASES  # noqa # necessary for setup

SECRET_KEY = get_random_string()

INSTALLED_APPS = ['tests.test_managers']
DATABASE_ROUTERS = ["salesforce.router.ModelRouter"]
SF_LAZY_CONNECT = True
USE_TZ = True
