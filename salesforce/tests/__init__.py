"This is necessary only with Django 1.5.x or older."

# Nothing common useful for tests can be here.
# It can not be used by sub-modules due to consequence of cyclic dependencies.
# Independent modules with own models can not also import anything under this
# path, because they shouldn't be forced to import example.models due to risk
# of errors in models validation.

from salesforce import DJANGO_16_PLUS
if not DJANGO_16_PLUS:
	from salesforce.tests.test_auth import *
	from salesforce.tests.test_integration import *
	from salesforce.tests.test_browser import *
	from salesforce.tests.test_ssl import *
	from salesforce.tests.test_unit import *
	from salesforce.tests.test_utils import *
