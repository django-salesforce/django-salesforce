from salesforce.testrunner.settings import *

SF_LAZY_CONNECT = True
DATABASES = {'default': DATABASES['default'],
		'salesforce': DATABASES['salesforce']}
DATABASES['salesforce']['HOST'] = 'https://nonsense.example.com'
INSTALLED_APPS += ('tests.test_lazy_connect',)
