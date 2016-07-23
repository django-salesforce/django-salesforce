"""Test the completness ad validity of inspectdb by read and write for all tables.

It tries to find model and read one record from all retrieveable tables, except
objects with extraordinal filter conditions (3%). Then it tries to write this
record back if the table is updateable, except some tables (5%). This can fail
on permissions.

Usage:
$ python manage.py inspectdb --database=salesforce >tests/inspectdb/models.py
$ python manage.py check
$ python tests/inspectdb/slow_test.py
"""

from sys import stdout, stderr
import os
import sys

import django
from salesforce.backend.base import SalesforceError

from tests.inspectdb import models as mdl

sys.path.insert(0, '.')
os.environ['DJANGO_SETTINGS_MODULE'] = 'tests.inspectdb.settings'
from django.db import connections  # NOQA
# The same "django.setup()" is used by manage.py subcommands in Django
django.setup()

sf = connections['salesforce']


def run():
    start_name = sys.argv[1] if sys.argv[1:] else ''
    n_tables = n_read = n_no_data = n_read_errors = n_write = n_write_errors = 0
    for tab in sf.introspection.table_list_cache['sobjects']:
        if tab['retrieveable'] and not tab['name'] in (
                # These require specific filters (descried in their error messages)
                'CollaborationGroupRecord', 'ContentFolderMember', 'ContentFolderItem',
                'ContentDocumentLink', 'Idea', 'IdeaComment', 'UserProfileFeed',
                'Vote',  # 'OpportunityPartner', 'Product2Feed',
                # TODO The "RecordType" is a very important object, but it can fail
                # on philchristensen's Salesforce with Travis. It should be more
                # investigated to which SObject is the RecordType related and enabled
                # again.
                'RecordType',
                # UNKNOWN_EXCEPTION:
                'TenantUsageEntitlement',
        ):
            if tab['name'] < start_name:
                continue
            [test_class] = [cls for cls in (getattr(mdl, x) for x in dir(mdl))
                            if (isinstance(cls, type) and
                                issubclass(cls, django.db.models.Model) and
                                cls._meta.db_table == tab['name'])
                            ]
            stdout.write('%s ' % tab['name'])
            obj = None
            try:
                n_read += 1
                obj = test_class.objects.all()[0]
            except SalesforceError as e:
                stderr.write("\n************** %s %s\n" % (tab['name'], e))
                n_read_errors += 1
            except IndexError:
                n_no_data += 1
            if obj:
                stdout.write("* ")
            if obj and tab['updateable'] and not tab['name'] in (
                    # Cannot modify managed objects
                    'ApexClass', 'ApexComponent', 'ApexTrigger', 'FieldPermissions',
                    'ObjectPermissions', 'PermissionSet', 'Scontrol',
                    'StaticResource', 'WebLink',
                    # This is not writable due to 'NamespacePrefix' field
                    'ApexPage',
                    # Some Leads are not writable becase they are coverted to Contact
                    'Lead',
                    # Insufficient access rights on cross-reference id
                    'Group',
                    'OpportunityShare', 'Profile',
                    # Some very old items can have empty Folder.Name, but can
                    # not be saved again without Name.
                    'Folder',
                    # Records with some values of UserShare.RowCause can not be updated.
                    'UserShare',
                    # Cannot directly insert FeedItem with type TrackedChange
                    'FeedItem',
            ):
                stdout.write('(write) ')
                try:
                    n_write += 1
                    obj.save(force_update=True)
                except SalesforceError as e:
                    stderr.write("\n************** %s %s\n" % (tab['name'], e))
                    n_write_errors += 1
                else:
                    # object 'Topic' doesn't have the attribute 'last_modified_date'
                    # in recently created SFDC databases (proably version 34.0+)
                    if hasattr(obj, 'last_modified_date'):
                        assert test_class.objects.get(pk=obj.pk).last_modified_date > obj.last_modified_date
            stdout.write('\n')
    n_tables = len(sf.introspection.table_list_cache['sobjects'])
    print('Result: {n_tables} tables, {n_read} reads tried, {n_no_data} no data, '
          '{n_read_errors} read errors, {n_write} writes tried, {n_write_errors} write errors'
          .format(n_tables=n_tables, n_read=n_read, n_no_data=n_no_data,
                  n_read_errors=n_read_errors, n_write=n_write, n_write_errors=n_write_errors))
    print('********* ERRORs found' if n_read_errors + n_write_errors else 'OK')
    return n_read_errors + n_write_errors == 0

if __name__ == '__main__':
    ok = run()
    sys.exit(0 if ok else 1)
