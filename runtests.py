#This file mainly exists to allow python setup.py test to work.

# Copied from
# http://ericholscher.com/blog/2009/jun/29/enable-setuppy-test-your-django-apps/

import os, sys
os.environ['DJANGO_SETTINGS_MODULE'] = 'salesforce.testrunner.settings'
test_dir = os.path.dirname(__file__)
sys.path.insert(0, test_dir)
sys.path.insert(0, '/home/hynek/tmp/django-salesforce-jacobwegner/salesforce/tests')

from django.test.utils import get_runner
from django.conf import settings

def runtests():
    test_runner = get_runner(settings)
    failures = test_runner([], verbosity=2, interactive=True)
    import pdb; pdb.set_trace()
    sys.exit(failures)

if __name__ == '__main__':
    runtests()
