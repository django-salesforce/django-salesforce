from salesforce.testrunner.settings import *

SF_LAZY_CONNECT = True
# backup the static setting and set an empty dynamic setting
DATABASES = {
	'default': DATABASES['default'],
	'salesforce_copy': DATABASES['salesforce'],
	'salesforce': {
		'ENGINE': 'salesforce.backend',
		'HOST': 'https://nonsense.example.com',
		'CONSUMER_KEY': '.',
		'CONSUMER_SECRET': '.',
		'USER': 'dynamic auth',
		'PASSWORD': '.',
	}
}
INSTALLED_APPS += ('tests.test_dynamic_auth',)
