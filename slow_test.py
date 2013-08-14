"""Test introspection
# Backup example/models.py
$ python manage.py inspectdb --database=salesforce >salesforce/testrunner/example/models.py
$ python manage.py validate
$ python manage.py shell
>>>  execfile('slow_test.py')
  (that tries to read ane record from all retrieveable tables, except 4 with extraordinal filter conditions
   and tries to write this record back if the table is updateable, except 11 tables.)

# Restore example/models.py
"""

from django.db import connections
from salesforce.testrunner.example import models as mdl
from sys import stdout, stderr
import django
import pprint
import salesforce

sf = connections['salesforce']
#cur = sf.cursor()
pp = pprint.PrettyPrinter(width=200).pprint

for tab in sf.introspection.table_list_cache['sobjects']:
    if tab['retrieveable'] and not tab['name'] in (
        'ContentDocumentLink',  'Idea', 'UserProfileFeed', 'Vote', # These require a specific filter
            ):
        xx = [getattr(mdl, x) for x in dir(mdl)
                if isinstance(getattr(mdl, x), type) and issubclass(getattr(mdl, x), django.db.models.Model) and
                        getattr(mdl, x)._meta.db_table == tab['name']
            ][0]
        stdout.write('%s ' % tab['name'])
        try:
            x = list(xx.objects.all()[:1])
        except salesforce.backend.base.SalesforceError, e:
                stderr.write("\n************** %s %s" % (tab['name'], e))
                x = None
        if x:
            stdout.write("* ")
        if x and tab['updateable'] and  not tab['name'] in (
                'ApexClass', 'ApexComponent', 'ApexTrigger', 'FieldPermissions', 'ObjectPermissions', 'PermissionSet', 'Scontrol', 'StaticResource', 'WebLink', # Cannot modify managed object
                'ApexPage', # this is not writable due to 'NamespacePrefix' field
                'Group',  # Insufficient access rights on cross-reference id
                ):
            stdout.write('(write) ')
            try:
                x[0].save(force_update=True)
            except salesforce.backend.base.SalesforceError, e:
                stderr.write("\n************** %s %s" % (tab['name'], e))
            else:
                assert xx.objects.get(pk=x[0].pk).lastmodifieddate > x[0].lastmodifieddate
        stdout.write('\n')
