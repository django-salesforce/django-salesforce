from salesforce.testrunner.settings import *  # NOQA
from salesforce.testrunner.settings import DATABASES, INSTALLED_APPS

SF_LAZY_CONNECT = True
DATABASES = {'default': DATABASES['default'],
             'salesforce': DATABASES['salesforce']}
ORIG_SALESFORCE_DB = DATABASES['salesforce'].copy()
DATABASES['salesforce'].update(dict(HOST='https://nonsense.example.com',
                                    CONSUMER_KEY='.',
                                    CONSUMER_SECRET='.',
                                    USER='.',
                                    PASSWORD='.'))
INSTALLED_APPS += ('tests.test_lazy_connect',)
