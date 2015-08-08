# These imports are necessary only with old Django 1.5.x and older.
# Nothing common useful for test sub-modules can be here, because
# modules inside should not create a cyclic dependency, independent
# modules shouldn't be forced to import example.models that causes
# validation errors.
from salesforce.tests.test_auth import *
from salesforce.tests.test_integration import *
from salesforce.tests.test_browser import *
from salesforce.tests.test_ssl import *
from salesforce.tests.test_unit import *
from salesforce.tests.test_utils import *

