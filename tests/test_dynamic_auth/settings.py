from salesforce.testrunner.settings import *

SF_LAZY_CONNECT = True
DATABASES['salesforce2'] = DATABASES['salesforce']
DATABASES['salesforce'] = {
		'ENGINE': 'salesforce.backend',
		'HOST': 'https://nonsense.example.com',
		'CONSUMER_KEY': '.',
		'CONSUMER_SECRET': '.',
		'USER': 'dynamic auth',
		'PASSWORD': '.',
		}
INSTALLED_APPS += ('tests.test_dynamic_auth',)
