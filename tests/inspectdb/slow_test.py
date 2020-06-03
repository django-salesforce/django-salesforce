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

from inspect import isclass
from sys import stdout, stderr
import os
import sys

import django
sys.path.insert(0, '.')
os.environ['DJANGO_SETTINGS_MODULE'] = 'tests.inspectdb.settings'

django.setup()

# these 3 lines must be imported after: path, environ, django.setup()
from django.db import connections  # NOQA
from tests.inspectdb import models as mdl  # NOQA
from salesforce.backend.base import SalesforceError  # NOQA


sf = connections['salesforce']


def run():
    start_name = sys.argv[1] if sys.argv[1:] else ''
    n_tables = n_read = n_no_data = n_read_errors = n_write = n_write_errors = 0
    model_map = {cls._meta.db_table: cls
                 for cls in mdl.__dict__.values()
                 if isclass(cls) and issubclass(cls, django.db.models.Model)
                 }
    problematic_read = {
        # These require specific filters (descried in their error messages)
        'CollaborationGroupRecord', 'ContentFolderMember', 'ContentFolderItem',
        'ContentDocumentLink', 'Idea', 'IdeaComment', 'UserProfileFeed',
        'Vote',  # 'OpportunityPartner', 'Product2Feed',
        # UNKNOWN_EXCEPTION:
        'TenantUsageEntitlement',
        }
    problematic_write = {
        # Cannot modify managed objects
        'ApexClass', 'ApexComponent', 'ApexTrigger', 'FieldPermissions',
        'ObjectPermissions', 'PermissionSet', 'Scontrol',
        'StaticResource', 'WebLink', 'RecordType',
        # This is not writable due to 'NamespacePrefix' field
        'ApexPage',
        # It does not update the 'last_modified_date' field
        'AppMenuItem',
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
        # The Apex Class selected is not valid. An Apex Class that implements
        # the Messaging.InboundEmailHandler interface must be selected.
        'EmailServicesFunction',
        # A special user of type user_type='AutomatedProcess' exists in Users
        # since API 41.0 Winter'18.
        # That user account can not be saved because it has an invalid email.
        'User', 'UserLogin',
    }
    for tab in sf.introspection.table_list_cache['sobjects']:
        db_table = tab['name']
        # More sobjects are 'queryable' and 'retrieveable' than
        # only 'retrieveable', but half of them would be problematic.
        if tab['retrieveable'] and not db_table.endswith('ChangeEvent') and db_table not in problematic_read:
            if db_table < start_name:
                continue
            test_class = model_map[db_table]

            stdout.write('%s' % db_table)
            obj = None
            try:
                n_read += 1
                obj = test_class.objects.all()[0]
            except SalesforceError as exc:
                stderr.write("\n************** %s %s\n" % (db_table, exc))
                n_read_errors += 1
            except IndexError:
                n_no_data += 1
            if obj:
                stdout.write("* ")
            if obj and tab['updateable'] and db_table not in problematic_write:
                stdout.write('(write) ')
                try:
                    n_write += 1
                    obj.save(force_update=True)
                except SalesforceError as exc:
                    stderr.write("\n************** %s %s\n" % (db_table, exc))
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
