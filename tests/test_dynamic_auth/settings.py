from salesforce.testrunner.settings import *

SF_LAZY_CONNECT = True
assert 'salesforce2' in DATABASES
DATABASES['salesforce'] = {
		'ENGINE': 'salesforce.backend',
		'HOST': 'https://cs8.salesforce.com',
		'CONSUMER_KEY': '.',
		'CONSUMER_SECRET': '.',
		'USER': 'dynamic auth',
		'PASSWORD': '.',
		}
INSTALLED_APPS += ('tests.test_dynamic_auth',)
