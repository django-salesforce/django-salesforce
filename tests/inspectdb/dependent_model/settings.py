from salesforce.testrunner.settings import *  # NOQA
from salesforce.testrunner.settings import INSTALLED_APPS

INSTALLED_APPS = [x for x in INSTALLED_APPS if not x.startswith('salesforce.testrunner.')]
# INSTALLED_APPS += ('tests.inspectdb', 'tests.inspectdb.dependent_model')
INSTALLED_APPS += ['tests.inspectdb.dependent_model.AutoModelConf',
                   'tests.inspectdb.dependent_model.DependentModelConf']
ROOT_URLCONF = None
