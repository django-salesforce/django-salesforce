# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#
# pylint:disable=deprecated-method,invalid-name,protected-access,too-many-lines,unused-variable

from decimal import Decimal
from distutils.util import strtobool  # pylint: disable=no-name-in-module,import-error # venv inst pylint false positiv
import datetime
import logging
import os
import re
import warnings

import pytz
from django.conf import settings
from django.db import connections
from django.db.models import Q, Avg, Count, Sum, Min, Max, Model, query as models_query
from django.test import TestCase
from django.utils import timezone
from typing import Any, cast, List, TypeVar

import salesforce
from salesforce import router
from salesforce.backend import DJANGO_22_PLUS
from salesforce.backend.test_helpers import (  # NOQA pylint:disable=unused-import
    expectedFailure, expectedFailureIf, skip, skipUnless)
from salesforce.backend.test_helpers import (
    current_user, default_is_sf, sf_alias, uid_version as uid,
    QuietSalesforceErrors, LazyTestMixin)
from salesforce.dbapi.exceptions import SalesforceWarning
from salesforce.models import SalesforceModel
from salesforce.testrunner.example.models import (
        Account, Contact, Lead, User,
        ApexEmailNotification, BusinessHours, Campaign, CronTrigger,
        Opportunity, OpportunityContactRole,
        Product, Pricebook, PricebookEntry, Note, Task,
        Organization, models_template,
        )

log = logging.getLogger(__name__)

_M = TypeVar('_M', bound=Model)

QUIET_KNOWN_BUGS = strtobool(os.getenv('QUIET_KNOWN_BUGS', 'false'))
test_email = 'test-djsf-unittests%s@example.com' % uid
sf_databases = [db for db in connections if router.is_sf_database(db)]

_sf_tables = []  # type: List[str]


def sf_tables() -> List[str]:
    if not _sf_tables and default_is_sf:
        for x in connections[sf_alias].introspection.table_list_cache['sobjects']:
            _sf_tables.append(x['name'])
    return _sf_tables


def refresh(obj: _M) -> _M:
    """Get the same object refreshed from the same db.
    """
    db = obj._state.db
    qs = type(obj).objects.using(db)  # type: models_query.QuerySet[_M]
    return qs.get(pk=obj.pk)


class BasicSOQLRoTest(TestCase, LazyTestMixin):
    """Tests that need no setUp/tearDown"""
    # pylint:disable=no-self-use,pointless-statement

    databases = '__all__'

    @classmethod
    def setUpClass(cls) -> None:
        """Add contact if less than 2 exist"""
        super(BasicSOQLRoTest, cls).setUpClass()
        if User.objects.count() == 0:
            User.objects.create(Username=current_user)
        some_accounts = list(Account.objects.all()[:1])
        if not some_accounts:
            some_accounts = [Account.objects.create(Name='sf_test account_0')]
        some_contacts = Contact.objects.exclude(account__isnull=True).filter(name__gt='A')[:2]
        if len(some_contacts) < 2:
            for i in range(2 - len(some_contacts)):
                Contact.objects.create(first_name='sf_test demo', last_name='Test %d' % i,
                                       account=some_accounts[0])

    @skipUnless(default_is_sf, "Default database should be any Salesforce.")
    def test_raw(self) -> None:
        """Read two contacts by raw.

        (At least 3 manually created Contacts must exist before these read-only tests.)
        """
        with self.lazy_assert_n_requests(1):
            contacts = list(Contact.objects.raw(
                "SELECT Id, LastName, FirstName FROM Contact "
                "LIMIT 2"))
        with self.lazy_assert_n_requests(0):
            self.assertEqual(len(contacts), 2)
            # It had a side effect that the same assert failed second times.
            self.assertEqual(len(contacts), 2)
            '%s' % contacts[0].__dict__  # Check that all fields are accessible
        self.lazy_check()

    @skipUnless(default_is_sf, "Default database should be any Salesforce.")
    def test_raw_translations(self) -> None:
        """Read a Contact raw and translate it to Lead fields."""
        contact = Contact.objects.all()[0]
        false_lead_raw = list(Lead.objects.raw(
            "SELECT Id, LastName FROM Contact WHERE Id=%s", params=[contact.pk],
            translations={'LastName': 'Company'}))
        self.assertEqual(len(false_lead_raw), 1)
        self.assertEqual(false_lead_raw[0].Company, contact.last_name)

    @skipUnless(default_is_sf, "Default database should be any Salesforce.")
    def test_raw_foreignkey_id(self) -> None:
        """Get the first two contacts by raw query with a ForeignKey id field.
        """
        with self.lazy_assert_n_requests(1):
            contacts = list(Contact.objects.raw(
                "SELECT Id, LastName, FirstName, OwnerId FROM Contact "
                "LIMIT 2"))
        len(contacts)
        self.assertEqual(len(contacts), 2)
        with self.lazy_assert_n_requests(0):
            '%s' % contacts[0].__dict__  # Check that all fields are accessible
        with self.lazy_assert_n_requests(1):
            self.assertIn('@', contacts[0].owner.Email)
        self.lazy_check()

    def test_select_all(self) -> None:
        """Get the first two contact records.
        """
        contacts = Contact.objects.all()[0:2]
        self.assertEqual(len(contacts), 2)

    @skipUnless(default_is_sf, "Default database should be any Salesforce.")
    def test_foreign_key(self) -> None:
        """Verify that the owner of an Contact is the currently logged admin.
        """
        current_sf_user = User.objects.get(Username=current_user)
        test_contact = Contact(first_name='sf_test', last_name='my')
        test_contact.save()
        try:
            contact = Contact.objects.filter(owner=current_sf_user)[0]
            user = contact.owner
            # This user can be e.g. 'admins@freelancersunion.org.prod001'.
            self.assertEqual(user.Username, current_user)
        finally:
            test_contact.delete()

    def test_foreign_key_column(self) -> None:
        """Verify filtering by a column of related parent object.
        """
        test_account = Account(Name='sf_test account')
        test_account.save()
        test_contact = Contact(first_name='sf_test', last_name='my', account=test_account)
        test_contact.save()
        try:
            contacts = Contact.objects.filter(account__Name='sf_test account')
            self.assertEqual(len(contacts), 1)
        finally:
            test_contact.delete()
            test_account.delete()

    def test_select_related(self) -> None:
        """Verify that select_related does not require additional queries.
        """
        test_account = Account(Name='sf_test account')
        test_account.save()
        test_contact = Contact(first_name='sf_test', last_name='my', account=test_account)
        test_contact.save()
        try:
            with self.lazy_assert_n_requests(1):
                qs = Contact.objects.filter(account__Name='sf_test account').select_related('account')
                contacts = list(qs)
            with self.lazy_assert_n_requests(0):  # this fails in Django 2.0 - not cached
                [x.account.Name for x in contacts]
            self.assertGreaterEqual(len(contacts), 1)
            self.lazy_check()
        finally:
            test_contact.delete()
            test_account.delete()

    def test_select_related_child_subquery(self) -> None:
        """Test select_related with a subquery by children objects.
        """
        with self.lazy_assert_n_requests(1):
            qs = Account.objects.filter(contact__isnull=False, Owner__isnull=False).select_related('Owner')
            if 'AND Contact.Id' in str(qs.query):
                sql_end = 'FROM Contact WHERE (Contact.Account.OwnerId != null AND Contact.Id != null)'
            else:
                sql_end = 'FROM Contact WHERE (Contact.Id != null AND Contact.Account.OwnerId != null)'
            self.assertTrue(sql_end, str(qs.query))
            self.assertGreater(len(list(qs)), 0)
            self.assertGreater(qs[0].Owner.Username, '')

    def test_select_related_child_filter(self) -> None:
        """Test select_related with a subquery by children objects.
        """
        with self.lazy_assert_n_requests(1):
            subquery = Contact.objects.filter().values('account_id')
            qs = Account.objects.filter(pk__in=subquery).select_related('Owner')
            self.assertGreater(len(qs), 0)
            self.assertGreater(qs[0].Owner.Username, '')
        soql = str(qs.query)
        self.assertTrue(soql.endswith("FROM Account WHERE Account.Id IN (SELECT Contact.AccountId FROM Contact)"))

    def test_select_related_child_exclude(self) -> None:
        """Test select_related with a subquery by children objects.
        """
        # We use 'not_in' lookup, because this is not supported: 'exclude(pk__in=subsuery)'
        #     Account.objects.exclude(contact__isnull=True)

        with self.lazy_assert_n_requests(1):
            subquery = Contact.objects.values('account_id')
            qs = Account.objects.filter(pk__not_in=subquery).select_related('Owner')
            list(qs)
        soql = str(qs.query)
        self.assertTrue(soql.endswith("FROM Account WHERE Account.Id NOT IN (SELECT Contact.AccountId FROM Contact)"))

        # the same without 'not_in' lookup by two requests and exclude()
        with self.lazy_assert_n_requests(2):
            sub_ids = Contact.objects.filter(account_id__gt='').values_list('account_id', flat=True)[:100]
            qs = Account.objects.exclude(pk__in=list(sub_ids)).select_related('Owner')
            list(qs)
        soql = str(qs.query)
        self.assertRegex(soql, r"FROM Account WHERE \(NOT \(Account.Id IN \((?:NULL, )?'001\w{15}'")

    def test_not_eq(self) -> None:
        qs = Contact.objects.filter(email__not_eq='')
        self.assertTrue(all(x.email > '' for x in qs))

    @skipUnless(default_is_sf, "Default database should be any Salesforce.")
    def test_one_to_one_field(self) -> None:
        # test 1a is unique field
        self.assertEqual(ApexEmailNotification._meta.get_field('user').unique, True)

        current_sf_user = User.objects.get(Username=current_user)
        orig_objects = list(ApexEmailNotification.objects.filter(
            Q(user=current_sf_user) | Q(email='apex.bugs@example.com')))
        _ = orig_objects  # NOQA
        try:
            notifier_u = current_sf_user.apex_email_notification
            new_u = None
        except ApexEmailNotification.DoesNotExist:
            notifier_u = new_u = ApexEmailNotification(user=current_sf_user)
            notifier_u.save()
        try:
            notifier_e = ApexEmailNotification.objects.get(email='apex.bugs@example.com')
            new_e = None
        except ApexEmailNotification.DoesNotExist:
            notifier_e = new_e = ApexEmailNotification(email='apex.bugs@example.com')
            notifier_e.save()

        try:
            # test 1b is unique value
            duplicate = ApexEmailNotification(user=current_sf_user)
            # the method self.assertRaise was too verbose about exception
            try:
                with QuietSalesforceErrors(sf_alias):
                    duplicate.save()
            except salesforce.backend.base.SalesforceError as exc:
                # TODO uncovered line, baybe bug
                self.assertEqual(exc.data[0]['errorCode'], 'DUPLICATE_VALUE')  # type: ignore
            else:
                self.assertRaises(salesforce.backend.base.SalesforceError, duplicate.save)

            # test 2: the reverse relation is a value, not a set
            users = User.objects.exclude(apex_email_notification__user=None)
            self.assertIn(current_user, [x.Username for x in users])

            # test 3: relation to the parent
            result = ApexEmailNotification.objects.filter(user__Username=notifier_u.user.Username)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0].user_id, notifier_u.user_id)
        finally:
            if new_u:
                new_u.delete()
            if new_e:
                new_e.delete()

        # this had fail, therefore moved at the end and itemized for debugging
        # qs = User.objects.exclude(apex_email_notification=None)
        # print(qs.query.get_compiler('salesforce').as_sql())
        # list(qs)
        list(User.objects.exclude(apex_email_notification=None))

    def test_update_date(self) -> None:
        """Test updating a date.
        """
        # removed microseconds only for easy compare in the test, no problem
        now = timezone.now().replace(microsecond=0)
        contact = Contact(first_name='sf_test', last_name='my')
        contact.save()
        contact = refresh(contact)
        try:
            contact.email_bounced_date = now
            contact.save()
            self.assertEqual(refresh(contact).email_bounced_date, now)
        finally:
            contact.delete()

    def test_insert_date(self) -> None:
        """Test inserting a date.
        """
        now = timezone.now().replace(microsecond=0)
        contact = Contact(first_name='Joe', last_name='Freelancer', email_bounced_date=now)
        contact.save()
        try:
            self.assertEqual(refresh(contact).email_bounced_date, now)
        finally:
            contact.delete()

    @skipUnless(default_is_sf, "Default database should be any Salesforce.")
    def test_default_specified_by_sf(self) -> None:
        """Verify insert of object with a field with default value on create by SF.

        (The default is used only for a field unspecified in SF REST API, but
        not for None or any similar value. It was a pain for some unimportant
        foreign keys that don't accept null.)
        """
        # Verify a smart default is used.
        contact = Contact(first_name='sf_test', last_name='my')
        contact.save()
        try:
            self.assertEqual(refresh(contact).owner.Username, current_user)
        finally:
            contact.delete()
        # Verify that an explicit value is possible for this field.
        other_user_obj = User.objects.exclude(Username=current_user).filter(IsActive=True)[0]
        contact = Contact(first_name='sf_test', last_name='your',
                          owner=other_user_obj)
        contact.save()
        try:
            self.assertEqual(refresh(contact).owner.Username, other_user_obj.Username)
        finally:
            contact.delete()

    def test_not_null_related(self) -> None:
        """Verify conditions `isnull` for foreign keys: filter(Account=None)

        filter(Account__isnull=True) and nested in Q(...) | Q(...).
        """
        test_contact = Contact(first_name='sf_test', last_name='my')
        test_contact.save()
        try:
            contacts = Contact.objects.filter(
                Q(account__isnull=True) | Q(account=None),
                account=None,
                account__isnull=True,
                first_name='sf_test'
            )
            self.assertEqual(len(contacts), 1)
        finally:
            test_contact.delete()

    def test_unicode(self) -> None:
        """Make sure weird unicode breaks properly.
        """
        test_lead = Lead(FirstName='\u2603', LastName="Unittest Unicode",
                         Email='test-djsf-unicode-email@example.com',
                         Company="Some company")
        test_lead.save()
        try:
            self.assertEqual(refresh(test_lead).FirstName, '\u2603')
        finally:
            test_lead.delete()

    def test_date_comparison(self) -> None:
        """Test that date comparisons work properly.
        """
        today = datetime.datetime(2013, 8, 27)
        if settings.USE_TZ:
            today = timezone.make_aware(today, pytz.utc)
        yesterday = today - datetime.timedelta(days=1)
        tomorrow = today + datetime.timedelta(days=1)
        contact = Contact(first_name='sf_test' + uid, last_name='date',
                          email_bounced_date=today)
        contact.save()
        try:
            contacts1 = Contact.objects.filter(email_bounced_date__gt=yesterday, first_name='sf_test' + uid)
            self.assertEqual(len(contacts1), 1)
            contacts2 = Contact.objects.filter(email_bounced_date__gt=tomorrow, first_name='sf_test' + uid)
            self.assertEqual(len(contacts2), 0)
        finally:
            contact.delete()

    @skipUnless(default_is_sf, "Default database should be any Salesforce.")
    def test_insert(self) -> None:
        """Create a lead record, and make sure it ends up with a valid Salesforce ID.
        """
        test_lead = Lead(FirstName="User", LastName="Unittest Inserts",
                         Email='test-djsf-inserts-email@example.com',
                         Company="Some company")
        test_lead.save()
        try:
            self.assertEqual(len(test_lead.pk), 18)
        finally:
            test_lead.delete()

    @skipUnless(default_is_sf, "Default database should be any Salesforce.")
    def test_double_save(self) -> None:
        """Double save without refresh of an object with a DEFAULTED_ON_CREATE
        field should not cause a problem.
        """
        oppo = Opportunity(name='test op', stage='Prospecting', close_date=datetime.date.today())
        try:
            oppo.save()
            with self.assertWarns(SalesforceWarning):
                # should save a DEFAULTED_ON_CREATE field 'probability' on update, but with warning
                oppo.save()

            oppo.save(update_fields=['name', 'stage'])
            with self.assertWarns(SalesforceWarning):
                oppo.save(update_fields=['name', 'stage', 'probability'])

            # a normal value can be saved on update
            oppo.probability = '25'  # percent
            oppo.save()
        finally:
            oppo.delete()

    def test_delete(self) -> None:
        """Create a lead record, then delete it, and make sure it's gone.
        """
        test_lead = Lead(FirstName="User", LastName="Unittest Deletes",
                         Email='test-djsf-delete-email@example.com',
                         Company="Some company")
        test_lead.save()
        test_lead.delete()

        self.assertRaises(Lead.DoesNotExist, Lead.objects.get, Email='test-djsf-delete-email@example.com')

    @skipUnless(default_is_sf, "Default database should be any Salesforce.")
    def test_decimal_precision(self) -> None:
        """Verify the exact precision of the saved and retrived DecimalField
        """
        product = Product(Name="test Product")
        product.save()

        # The price for a product must be set in the standard price book.
        # http://www.salesforce.com/us/developer/docs/api/Content/sforce_api_objects_pricebookentry.htm
        pricebook = Pricebook.objects.get(Name="Standard Price Book")
        unit_price = Decimal('1234.56')
        saved_pricebook_entry = PricebookEntry(Product2=product, Pricebook2=pricebook,
                                               UnitPrice=unit_price, UseStandardPrice=False)
        saved_pricebook_entry.save()
        retrieved_pricebook_entry = PricebookEntry.objects.get(pk=saved_pricebook_entry.pk)

        try:
            self.assertEqual(saved_pricebook_entry.UnitPrice, unit_price)
            self.assertEqual(retrieved_pricebook_entry.UnitPrice, unit_price)
        finally:
            retrieved_pricebook_entry.delete()
            product.delete()

    def test_zero_decimal_places(self) -> None:
        """Test that DecimalField with decimal_places=0 is correctly parsed"""
        campaign = Campaign(name='test something', number_sent=3)
        campaign.save()
        try:
            ret = Campaign.objects.filter(number_sent=3)
            # should be parsed without ".0"
            val = ret[0].number_sent
            self.assertEqual(repr(val), "Decimal('3')")
            self.assertEqual(str(val), "3")
        finally:
            campaign.delete()

    def test_simple_custom_object(self) -> None:
        """Create, read and delete a simple custom object `django_Test__c`.
        """
        from salesforce.testrunner.example.models import Attachment, Test
        if 'django_Test__c' not in sf_tables():
            self.skipTest("Not found custom object 'django_Test__c'")
        results = Test.objects.all()[0:1]
        obj = Test(test_text='sf_test')
        obj.save()
        attachment = Attachment(name='test attachment', parent=obj)
        attachment.save()
        try:
            results = Test.objects.all()[0:1]
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].test_text, 'sf_test')
        finally:
            attachment.delete()
            obj.delete()

    def test_datetime_miliseconds(self) -> None:
        """Verify that a field with milisecond resolution is readable.
        """
        triggers = CronTrigger.objects.all()
        if not triggers:
            self.skipTest("No object with milisecond resolution found.")
        self.assertTrue(isinstance(triggers[0].PreviousFireTime, datetime.datetime))
        # The reliability of this is only 99.9%, therefore it is commented out.
        # self.assertNotEqual(trigger.PreviousFireTime.microsecond, 0)

    @skipUnless(default_is_sf, "Default database should be any Salesforce.")
    def test_time_field(self) -> None:
        """Test a TimeField (read, modify, verify).
        """
        obj_orig = BusinessHours.objects.all()[0]
        obj = refresh(obj_orig)
        self.assertTrue(isinstance(obj.MondayStartTime, datetime.time))
        obj.MondayStartTime = datetime.time(23, 59)
        obj.save()
        obj = refresh(obj)
        try:
            self.assertEqual(obj.MondayStartTime, datetime.time(23, 59))
        finally:
            obj_orig.save()

    def test_account_insert_delete(self) -> None:
        """Test insert and delete an account (normal or personal SF config)
        """
        if settings.PERSON_ACCOUNT_ACTIVATED:
            test_account = Account(FirstName='IntegrationTest',  # type: ignore[misc] # noqa # skip this branch
                                   LastName='Account')
        else:
            test_account = Account(Name='IntegrationTest Account')
        test_account.save()
        try:
            accounts = Account.objects.filter(Name='IntegrationTest Account')
            self.assertEqual(len(accounts), 1)
        finally:
            test_account.delete()

    def test_similarity_filter_operators(self) -> None:
        """Test filter operators that use LIKE 'something%' and similar.
        """
        User.objects.get(Username__exact=current_user)
        User.objects.get(Username__iexact=current_user.upper())
        User.objects.get(Username__contains=current_user[1:-1])
        User.objects.get(Username__icontains=current_user[1:-1].upper())
        User.objects.get(Username__startswith=current_user[:-1])
        User.objects.get(Username__istartswith=current_user[:-1].upper())
        User.objects.get(Username__endswith=current_user[1:])
        User.objects.get(Username__iendswith=current_user[1:].upper())
        # Operators regex and iregex not tested because they are not supported.

    @skipUnless(default_is_sf, "Default database should be any Salesforce.")
    def test_bulk_create(self) -> None:
        """Create two Contacts by one request in one command, find them.
        """
        account = Account(Name='test bulk')
        account.save()
        try:
            objects = [Contact(last_name='sf_test a', account=account),
                       Contact(last_name='sf_test b', account=account)]

            with self.lazy_assert_n_requests(1):
                ret = Contact.objects.bulk_create(objects)
                # test that can return ids from bulk_create
                self.assertEqual(len(set(x.pk for x in ret if x.pk)), 2)

            self.assertEqual(len(Contact.objects.filter(account=account)), 2)
            self.lazy_check()
        finally:
            account.delete()

    @skipUnless(default_is_sf, "Default database should be any Salesforce.")
    def test_queryset_update(self) -> None:
        """Update two Accounts by one request, after searching them by one request.
        """
        account_0, account_1 = [Account(Name='test' + uid), Account(Name='test' + uid)]
        account_0.save()
        account_1.save()
        try:
            # 2x update with different filters by primary key: 1 request per update
            with self.lazy_assert_n_requests(1):
                Account.objects.filter(pk=account_0.pk).update(Name="test2" + uid)
            with self.lazy_assert_n_requests(1):
                Account.objects.filter(pk__in=[account_1.pk]).update(Name="test2" + uid)

            # 1x update of 2 records + 1 more complicated filter == 2 requests
            with self.lazy_assert_n_requests(2):
                Account.objects.filter(pk__in=Account.objects.filter(Name='test2' + uid)).update(Name="test3" + uid)
            self.assertEqual(Account.objects.filter(Name='test3' + uid).count(), 2)
            self.lazy_check()
        finally:
            account_0.delete()
            account_1.delete()

    @skipUnless(default_is_sf, "Default database should be any Salesforce.")
    def test_bulk_delete_and_update(self) -> None:
        """Delete two Accounts by one request.
        """
        account_0, account_1 = [Account(Name='test' + uid), Account(Name='test' + uid)]
        account_0.save()
        account_1.save()
        try:
            result_count = 2
            with self.lazy_assert_n_requests(2):
                ret = Account.objects.filter(Name='test' + uid).delete()  # type: Any
            self.assertEqual(ret, (2, {'example.Account': 2}))
            result_count = Account.objects.filter(Name='test' + uid).count()
            self.assertEqual(result_count, 0)
            self.lazy_check()
        finally:
            if result_count:
                account_0.delete()
                account_1.delete()
        try:
            nn = 200
            pks = []
            objects = [Lead(Company='sf_test lead', LastName='name_{}'.format(i))
                       for i in range(nn)]
            with self.lazy_assert_n_requests(1):
                ret = Lead.objects.bulk_create(objects)
            pks = [x.pk for x in objects if x.pk]
            with self.lazy_assert_n_requests(1):
                ret = Lead.objects.filter(pk__in=pks).update(Company='sf_test lead_2')
        finally:
            if pks:
                with self.lazy_assert_n_requests(1):
                    ret = Lead.objects.filter(pk__in=pks).delete()

    @skipUnless(default_is_sf, "Default database should be any Salesforce.")
    def test_bulk_delete_all(self) -> None:
        PricebookEntry.objects.filter(pk__gt='').delete()

    def test_escape_single_quote(self) -> None:
        """Test single quotes in strings used in a filter

        Verity that they are escaped properly.
        """
        account_name = '''Dr. Evil's Giant\\' "Laser", LLC'''
        account = Account(Name=account_name)
        account.save()
        try:
            self.assertTrue(Account.objects.filter(Name=account_name).exists())
        finally:
            account.delete()

    @skipUnless(default_is_sf, "Default database should be any Salesforce.")
    def test_escape_single_quote_in_raw_query(self) -> None:
        """Test that manual escaping within a raw query is not double escaped.
        """
        account_name = '''test Dr. Evil's Giant\\' "Laser", LLC'''
        account = Account(Name=account_name)
        account.save()

        manually_escaped = '''test Dr. Evil\\'s Giant\\\\\\' "Laser", LLC'''
        try:
            retrieved_account = Account.objects.raw(
                "SELECT Id, Name FROM Account WHERE Name = '%s'" % manually_escaped)[0]
            self.assertEqual(account_name, retrieved_account.Name)
        finally:
            account.delete()

    def test_raw_query_empty(self) -> None:
        """Test that the raw query works even for queries with empty results.

        Raw queries with supported empty results are an improvement over normal
        Django. It is useful if some unimplemented features
        of django-salesforce are solved by writing a raw query.
        """
        len(list(Contact.objects.raw("SELECT Id, FirstName FROM Contact WHERE FirstName='nonsense'")))

    def test_range_simple(self) -> None:
        """Test simple range filters".
        """
        qs = Contact.objects.filter(Q(name__range=('c', 'e')))
        soql = qs.query.get_compiler('salesforce').as_sql()[0]
        self.assertIn("(Contact.Name >= %s AND Contact.Name <= %s)", soql)
        len(qs)

    def test_range_combined(self) -> None:
        """Test combined filters "a OR b AND c".
        """
        qs = Contact.objects.filter(Q(name='a') | Q(name__range=('c', 'e')))
        soql = qs.query.get_compiler('salesforce').as_sql()[0]
        self.assertIn("Contact.Name = %s OR (Contact.Name >= %s AND Contact.Name <= %s)", soql)
        len(qs)

    def test_range_lookup(self) -> None:
        """Get the test opportunity record by range condition.
        """
        test_opportunity = Opportunity(
                        name="Example Opportunity",
                        close_date=datetime.date(year=2015, month=7, day=30),
                        stage="Prospecting",
                        amount=130000.00
        )
        test_opportunity.save()
        try:
            # Test date objects
            start_date = datetime.date(year=2015, month=7, day=29)
            end_date = datetime.date(year=2015, month=8, day=1)
            oppy = Opportunity.objects.filter(close_date__range=(start_date, end_date))[0]
            self.assertEqual(oppy.name, 'Example Opportunity')
            self.assertEqual(oppy.stage, 'Prospecting')

            # Test datetime objects (now +- 10 minutes for clock inaccuracy)
            start_time = timezone.now() - datetime.timedelta(seconds=600)
            end_time = timezone.now() + datetime.timedelta(seconds=600)
            opportunities = Opportunity.objects.filter(created_date__range=(start_time, end_time))[:1]
            self.assertEqual(len(opportunities), 1, "Failed range filter or maybe incorrectly set clock")
            oppy = opportunities[0]
            self.assertEqual(oppy.name, 'Example Opportunity')
            self.assertEqual(oppy.stage, 'Prospecting')

            # Test DecimalField
            low_amount, high_amount = 100000.00, 140000.00
            oppy = Opportunity.objects.filter(amount__range=(low_amount, high_amount))[0]
            self.assertEqual(oppy.amount, 130000.00)

            # Test CharField
            low_letter, high_letter = 'E', 'G'
            oppy = Opportunity.objects.filter(name__range=(low_letter, high_letter))[0]
            self.assertEqual(oppy.name, 'Example Opportunity')
        finally:
            test_opportunity.delete()

    def test_combined_international(self) -> None:
        """Test combined filters with international characters.
        """
        # This is OK for long time
        len(Contact.objects.filter(Q(first_name='\xe1') & Q(last_name='\xe9')))
        # This was recently fixed
        len(Contact.objects.filter(Q(first_name='\xe1') | Q(last_name='\xe9')))
        len(Contact.objects.filter(Q(first_name='\xc3\xa1') | Q(last_name='\xc3\xa9')))

    @skipUnless(default_is_sf, "Default database should be any Salesforce.")
    def test_aggregate_query(self) -> None:
        """Test for different aggregate function.
        """
        test_product = Product(Name='test soap')
        test_product.save()
        test_product2 = Product(Name='test brush')
        test_product2.save()
        pricebook = Pricebook.objects.get(Name="Standard Price Book")
        PricebookEntry(Product2=test_product, Pricebook2=pricebook,
                       UseStandardPrice=False, UnitPrice=Decimal(100)).save()
        PricebookEntry(Product2=test_product2, Pricebook2=pricebook,
                       UseStandardPrice=False, UnitPrice=Decimal(80)).save()
        try:
            x_products = PricebookEntry.objects.filter(Name__startswith='test ')
            result = x_products.aggregate(Sum('UnitPrice'), Count('UnitPrice'), Avg('UnitPrice'),
                                          Min('UnitPrice'), Max('UnitPrice'))
            self.assertDictEqual(result, {'UnitPrice__sum': 180, 'UnitPrice__count': 2, 'UnitPrice__avg': 90.0,
                                          'UnitPrice__min': 80, 'UnitPrice__max': 100})
        finally:
            # dependent PricebookEntries are just deleted automatically by SF
            test_product.delete()
            test_product2.delete()

    @skipUnless(default_is_sf, "Default database should be any Salesforce.")
    def test_z_big_query(self) -> None:
        """Test a big query that will be splitted to more requests.

        Test it as late as possible.
        """
        cur = connections[sf_alias].cursor()
        cursor = cur.cursor
        cursor.execute("SELECT Id, Name FROM Lead", query_all=True)
        first_lead = cursor.fetchone()
        if first_lead:
            first_chunk_len = len(cursor._chunk)
            leads_list = [first_lead] + cursor.fetchall()
        else:
            first_chunk_len = 0
            leads_list = []
        if first_chunk_len == len(leads_list):
            self.assertLessEqual(len(leads_list), 2000, "Obsoleted constants")
            log.info("Not enough Leads accumulated (currently %d including deleted) "
                     "in the last two weeks that are necessary for splitting the "
                     "query into more requests. Number 2001 is enough.",
                     len(leads_list))
            self.skipTest("Not enough Leads found for big query test")

    @skipUnless(default_is_sf, "Default database should be any Salesforce.")
    def test_cursor_execute_fetch(self) -> None:
        """Get results by cursor.execute(...); fetchone(), fetchmany(), fetchall()
        """
        # TODO hy: fix for concurrency
        sql = "SELECT Id, LastName, FirstName, OwnerId FROM Contact LIMIT 2"
        cursor = connections[sf_alias].cursor()
        cursor.execute(sql)
        contacts = cursor.fetchall()
        self.assertEqual(len(contacts), 2)
        self.assertTrue(contacts[0][3].startswith('005'), "OwnerId must be an User.")
        cursor.execute(sql)
        self.assertEqual(cursor.fetchone(), contacts[0])
        self.assertEqual(cursor.fetchmany(), contacts[1:])

    @skipUnless(default_is_sf, "Default database should be any Salesforce.")
    def test_cursor_execute_aggregate(self) -> None:
        """Verify that aggregate queries can be executed directly by SOQL.
        """
        # Field 'Id' is very useful for COUNT over non empty fields.
        sql = "SELECT LastName, COUNT(Id) FROM Contact GROUP BY LastName LIMIT 2"
        cursor = connections[sf_alias].cursor()
        cursor.execute(sql)
        contact_aggregate = cursor.fetchone()
        self.assertEqual([x[0] for x in cursor.description], ['LastName', 'expr0'])
        self.assertEqual([type(x) for x in contact_aggregate], [str, int])
        self.assertGreaterEqual(contact_aggregate[1], 1)

    @skipUnless(default_is_sf, "Default database should be any Salesforce.")
    def test_cursor_list_plain_count(self) -> None:
        """Test that a plain COUNT() works with a list cursor.
        """
        cur = connections[sf_alias].cursor()
        cursor = cur.cursor
        cursor.execute("SELECT COUNT() FROM Contact")
        ret = cursor.fetchall()
        count = ret[0][0]
        self.assertTrue(isinstance(count, int))
        self.assertEqual(ret,  [[count]])

    @skipUnless(default_is_sf, "Default database should be any Salesforce.")
    def test_cursor_dict_plain_count(self) -> None:
        """Test that a plain COUNT() works with a dict cursor.
        """
        cur = connections[sf_alias]._cursor(name='dict')
        cursor = cur.cursor
        cursor.execute("SELECT COUNT() FROM Contact")
        ret = cursor.fetchall()
        self.assertEqual(ret,  [{'count': ret[0]['count']}])

    @skipUnless(default_is_sf, "Default database should be any Salesforce.")
    def test_group_by_compile(self) -> None:
        """Test that group annotations can be correctly compiled and executed"""
        qs = (Contact.objects.filter(account__Name__gt='').order_by()
              .values('account_id').annotate(cnt=Count('pk'))
              )
        soql, params = qs.query.get_compiler('salesforce').as_sql()
        expected_soql = (
            'SELECT Contact.AccountId, COUNT(Contact.Id) cnt FROM Contact '
            'WHERE Contact.Account.Name > %s GROUP BY Contact.AccountId'
        )
        self.assertEqual(soql, expected_soql)
        self.assertEqual(params, ('',))
        self.assertEqual(set(list(qs)[0].keys()), {'account_id', 'cnt'})

    @skipUnless(default_is_sf, "Default database should be any Salesforce.")
    def test_errors(self) -> None:
        """Test for improving code coverage.
        """
        # broken query raises exception
        bad_queryset = Lead.objects.raw("select XYZ from Lead")
        with QuietSalesforceErrors(sf_alias):
            self.assertRaises(salesforce.backend.base.SalesforceError, list, bad_queryset)

    def test_queryset_values(self) -> None:
        """Test list of dict qs.values()
        """
        values = Contact.objects.values()[:2]
        self.assertEqual(len(values), 2)
        self.assertIn('first_name', values[0])
        self.assertGreater(len(values[0]), 3)

    def test_queryset_values_names(self) -> None:
        """Test list of dict qs.values(*names) and list of tuples qs.values_list()
        """
        tmp = Contact.objects.values('pk', 'last_name')
        tmp[0]
        values = Contact.objects.values('pk', 'first_name', 'last_name')[:2]
        self.assertEqual(len(values), 2)
        self.assertIn('first_name', values[0])
        self.assertNotIn('attributes', values[0])
        self.assertEqual(len(values[0]), 3)
        if default_is_sf:
            self.assertRegex(cast(str, values[0]['pk']), '^003')

        values_list = Contact.objects.values_list('pk', 'first_name', 'last_name')[:2]
        self.assertEqual(len(values_list), 2)
        v0 = values[0]
        # it is a list in Django 2.1, but a tuple in Django 2.0
        self.assertEqual(list(values_list[0]), [v0['pk'], v0['first_name'], v0['last_name']])

    @skipUnless(default_is_sf, "Default database should be any Salesforce.")
    def test_double_delete(self) -> None:
        """Test that repeated delete of the same object is ignored

        the same way like "DELETE FROM Contact WHERE Id='deleted yet'" would do.
        """
        contact = Contact(last_name='sf_test',
                          owner=User.objects.get(Username=current_user))
        contact.save()
        contact_id = contact.pk
        Contact(pk=contact_id).delete()

        # Id of a deleted object or a too small valid Id shouldn't raise
        with warnings.catch_warnings(record=True) as w:
            Contact(pk=contact_id).delete()
            self.assertIs(w[-1].category, SalesforceWarning)
            self.assertIn('ENTITY_IS_DELETED', str(w[-1].message))
        # Simulate the same with obsoleted oauth session
        # It is not possible to use salesforce.auth.expire_token() to simulate
        # expiration because it forces reauhentication before the next request
        salesforce.auth.oauth_data[sf_alias]['access_token'] = 'something invalid/expired'
        with self.assertWarns(SalesforceWarning) as cm:
            Contact(pk=contact_id).delete()
            self.assertIn('ENTITY_IS_DELETED', cm.warnings[0].message.args[0])
        with self.assertWarns(SalesforceWarning) as cm:
            # Id of completely deleted item or fake but valid item.
            Contact(pk='003000000000000AAA').delete()
        # bad_id = '003000000000000AAB' # Id with an incorrect uppercase mask
        # self.assertRaises(salesforce.backend.base.SalesforceError, Contact(pk=bad_id).delete)

    @skipUnless(default_is_sf, "Default database should be any Salesforce.")
    @skipUnless(len(sf_databases) > 1, "Only one SF database found.")
    def test_multiple_sf_databases(self) -> None:
        """Test a connection to two sf sandboxes of the same organization.
        """
        other_db = [db for db in sf_databases if db != sf_alias][0]
        c1 = Contact(last_name='sf_test 1')
        c2 = Contact(last_name='sf_test 2')
        c1.save()
        c2.save(using=other_db)
        try:
            user1 = refresh(c1).owner
            user2 = refresh(c2).owner
            username1 = user1.Username
            username2 = user2.Username
            # Verify different usernames, like it is usual in sandboxes
            self.assertNotEqual(user1._state.db, user2._state.db)
            self.assertNotEqual(username1, username2)
            expected_user2 = connections[other_db].settings_dict['USER']
            self.assertEqual(username1, current_user)
            self.assertEqual(username2, expected_user2)
        finally:
            c1.delete()
            c2.delete()

    @skipUnless(default_is_sf, "Default database should be any Salesforce.")
    def test_expired_auth_id(self) -> None:
        """Test the code for expired auth ID for multiple SF databases.

        No similar test exists for a single db.
        """
        self.assertGreaterEqual(len(sf_databases), 1)
        objects = []
        for db in sf_databases:
            c = Contact(last_name='sf_test %s' % db)
            c.save(using=db)
            objects.append(c)
        try:
            # simulate that a request with invalid/expired auth ID re-authenticates
            # and succeeds.
            for db in sf_databases:
                salesforce.auth.oauth_data[db]['access_token'] += 'simulated invalid/expired'
            for x in objects:
                self.assertTrue(refresh(x))
        finally:
            for x in objects:
                x.delete()

    # This should not be implemented due to Django conventions.
    # def test_raw_aggregate(self):
    #    # raises "TypeError: list indices must be integers, not str"
    #    list(Contact.objects.raw("select Count() from Contact"))

    @skipUnless(default_is_sf, "Default database should be any Salesforce.")
    def test_only_fields(self) -> None:
        """Verify that access to "only" fields doesn't require a request, but others do.
        """
        # print([(x.id, x.last_name) for x in Contact.objects.only('last_name').order_by('id')[:2]])
        with self.lazy_assert_n_requests(0):
            sql = User.objects.only('Username').query.get_compiler('salesforce').as_sql()[0]
            self.assertEqual(sql, 'SELECT User.Id, User.Username FROM User')

        with self.lazy_assert_n_requests(1):
            user = User.objects.only('Username').order_by('pk')[0]

        # Verify that deferred fields work
        with self.lazy_assert_n_requests(0):
            user.pk
            user_username = user.Username
        self.assertIn('@', user_username)

        with self.lazy_assert_n_requests(1):
            self.assertGreater(len(user.LastName), 0)

        with self.lazy_assert_n_requests(1):
            self.assertEqual(user_username, User.objects.get(pk=user.pk).Username)

        with self.lazy_assert_n_requests(1):
            xx = Contact.objects.only('last_name').order_by('pk')[0]

        with self.lazy_assert_n_requests(0):
            xx.last_name

        with self.lazy_assert_n_requests(1):
            xy = Contact.objects.only('account').order_by('pk')[1]

        with self.lazy_assert_n_requests(0):
            xy.account_id

        with self.lazy_assert_n_requests(1):
            self.assertGreater(len(xy.last_name), 0)

        with self.lazy_assert_n_requests(0):
            xy.last_name

        self.lazy_check()

    @skipUnless(default_is_sf, "Default database should be any Salesforce.")
    def test_defer_fields(self) -> None:
        """Verify that access to a deferred field requires a new request, but others don't.
        """
        with self.lazy_assert_n_requests(1):
            contact = Contact.objects.defer('email')[0]
        with self.lazy_assert_n_requests(0):
            _ = contact.last_name
        with self.lazy_assert_n_requests(1):
            _ = contact.email
        self.lazy_check()
        _  # NOQA

    def test_incomplete_raw(self) -> None:
        """Test that omitted model fields can be queried by dot."""
        # with self.lazy_assert_n_requests(2):  # problem - Why too much requests?
        # raw query must contain the primary key (with the right capitalization, currently)
        with self.lazy_assert_n_requests(1):  # TODO why two requests?
            ret = list(Contact.objects.raw("select Id from Contact where FirstName != '' limit 2000"))
        with self.lazy_assert_n_requests(1):
            last_name = ret[0].last_name
        self.assertTrue(last_name and 'last' not in last_name.lower())
        with self.lazy_assert_n_requests(1):
            first_name = ret[0].first_name
        with self.lazy_assert_n_requests(0):
            last_name = ret[0].last_name
        assert first_name
        self.lazy_check()

    @skipUnless(default_is_sf, "Default database should be any Salesforce.")
    def test_filter_by_more_fk_to_the_same_model(self) -> None:
        """Test a filter with more relations to the same model.

        Verify that aliases are correctly decoded in the query compiler.
        """
        test_lead = Lead(Company='sf_test lead', LastName='name')
        test_lead.save()
        try:
            qs = Lead.objects.filter(pk=test_lead.pk,
                                     owner__Username=current_user,
                                     last_modified_by__Username=current_user)
            # Verify that a coplicated analysis is not performed on old Django
            # so that the query can be at least somehow simply compiled to SOQL
            # without exceptions, in order to prevent regressions.
            sql, params = qs.query.get_compiler('salesforce').as_sql()
            # Verify expected filters in SOQL compiled by new Django
            self.assertIn('Lead.Owner.Username = %s', sql)
            self.assertIn('Lead.LastModifiedBy.Username = %s', sql)
            # verify validity for SFDC, verify results
            refreshed_lead = qs.get()
            self.assertEqual(refreshed_lead.pk, test_lead.pk)
        finally:
            test_lead.delete()

    @skipUnless(default_is_sf, "Default database should be any Salesforce.")
    def test_filter_by_more_fk_to_the_same_model_subquery(self) -> None:
        """Test a filter with more relations to the same model.

        Verify that aliases are correctly decoded in the query compiler.
        """
        test_lead = Lead(Company='sf_test lead', LastName='name')
        test_lead.save()
        test_task = Task(who=test_lead)
        test_task.save()
        try:
            qs = Task.objects.filter(
                who__in=Lead.objects.filter(
                    pk=test_lead.pk,
                    owner__Username=current_user,
                    last_modified_by__Username=current_user)
            )
            sql, params = qs.query.get_compiler('salesforce').as_sql()
            self.assertRegex(sql, r'SELECT Task.Id, .* FROM Task WHERE Task.WhoId IN \(SELECT ')
            self.assertIn('Lead.Owner.Username = %s', sql)
            self.assertIn('Lead.LastModifiedBy.Username = %s', sql)
            refreshed_lead = qs[:1]
            self.assertEqual(len(refreshed_lead), 1)
        finally:
            test_task.delete()
            test_lead.delete()

    def test_many2many_relationship(self) -> None:
        """Verify that the related set of Many2Many relationship works

        Test for issue #55
        """
        contact = Contact.objects.all()[0]
        oppo = Opportunity(name='test op', stage='Prospecting', close_date=datetime.date.today())
        oppo.save()
        oc = OpportunityContactRole(opportunity=oppo, contact=contact, role='sponsor')
        oc.save()
        oc2 = OpportunityContactRole(opportunity=oppo, contact=contact, role='evaluator')
        oc2.save()
        try:
            qs = contact.opportunities.all()
            sql, params = qs.query.get_compiler('salesforce').as_sql()
            self.assertRegex(sql,
                             r'SELECT .*OpportunityContactRole\.Opportunity\.StageName.* '
                             'FROM OpportunityContactRole WHERE OpportunityContactRole.ContactId =')
            self.assertEqual([x.pk for x in qs], 2 * [oppo.pk])
        finally:
            oc2.delete()
            oc.delete()
            oppo.delete()

    def test_many2many_relationship_filter(self) -> None:
        """Verify that ManyToMany relationship can be filtered by a condition on remote object

        Test for PR #205
        """
        contact = Contact.objects.all()[0]
        oppo = Opportunity(name='test op', stage='Prospecting', close_date=datetime.date.today())
        oppo.save()
        oc = OpportunityContactRole(opportunity=oppo, contact=contact, role='sponsor')
        oc.save()
        oc2 = OpportunityContactRole(opportunity=oppo, contact=contact, role='evaluator')
        oc2.save()
        try:
            qs = Contact.objects.filter(opportunity_roles__opportunity__name='test op')
            self.assertEqual(list(qs), 2 * [contact])
            # self.assertEqual([x.pk for x in qs], 2 * [oppo.pk])
        finally:
            oc2.delete()
            oc.delete()
            oppo.delete()

    def test_filter_custom(self) -> None:
        """Verify that relations between custom and builtin objects

        are correctly compiled. (__r, __c etc.)
        """
        from salesforce.testrunner.example.models import Attachment, Test
        if 'django_Test__c' not in sf_tables():
            self.skipTest("Not found custom object 'django_Test__c'")
        qs = Attachment.objects.filter(parent__name='abc')
        # "SELECT Attachment.Id FROM Attachment WHERE Attachment.Parent.Name = 'abc'"
        list(qs)
        qs2 = Test.objects.filter(contact__last_name='Johnson')
        # "SELECT ... FROM django_Test__c WHERE django_Test__c.Contact__r.LastName = 'Johnson'")
        list(qs2)
        qs = Attachment.objects.filter(parent__in=Test.objects.filter(contact__last_name='Johnson'))
        list(qs)

    def test_using_none(self) -> None:
        alias = getattr(settings, 'SALESFORCE_DB_ALIAS', 'salesforce')
        self.assertEqual(Contact.objects.using(None)._db, alias)

    def test_dynamic_fields(self) -> None:
        """Test that fields can be copied dynamically from other model"""
        self.assertTrue(models_template)
        self.assertIn('@', Organization.objects.get().created_by.Username)

    def test_big_soql(self):
        """Test that a query of length almost 100000 is possible"""
        contact = Contact.objects.all()[0]
        # 4750 items * 21 characters == 99750
        qs = Contact.objects.filter(pk__in=4750 * [contact.pk])
        self.assertEqual(list(qs.values_list('pk', flat=True)), [contact.pk])

    def test_empty_slice(self):
        """Test queryset with empty slice - if high/low limits equals"""
        self.assertEqual(len(Contact.objects.all()[1:1]), 0)

# ============= Tests that need setUp Lead ==================


class BasicLeadSOQLTest(TestCase):
    """Tests that use a test Lead"""
    databases = '__all__'

    def setUp(self) -> None:
        """Create our test lead record.
        """
        def add_obj(obj):
            obj.save()
            self.objs.append(obj)
        #
        self.test_lead = Lead(
            FirstName="User" + uid,
            LastName="Unittest General",
            Email=test_email,
            Status='Open',
            Company="Some company, Ltd.",
        )
        self.objs = []  # type: List[SalesforceModel]
        self.test_lead.save()
        # This is only for demonstration that some test can be run even with
        # non SFDC database SALESFORCE_DB_ALIAS, even if the test expects some
        # contacts and the current user, but most of tests can pass only on SFDC.
        if not default_is_sf:
            add_obj(Contact(last_name='Test contact 1'))
            add_obj(Contact(last_name='Test contact 2'))
            add_obj(User(Username=current_user))

    def tearDown(self) -> None:
        """Clean up our test records.
        """
        if self.test_lead.pk is not None:
            self.test_lead.delete()
        for obj in self.objs:
            if obj.pk is not None:
                obj.delete()
        self.objs = []

    def test_exclude_query_construction(self) -> None:
        """Test that exclude query construction returns valid SOQL.
        """
        contacts = (Contact.objects.filter(first_name__isnull=False)
                    .exclude(email="steve@apple.com", last_name="Wozniak")
                    .exclude(last_name="smith"))
        number_of_contacts = contacts.count()
        self.assertIsInstance(number_of_contacts, int)
        # the default self.test_lead shouldn't be excluded by only one nondition
        leads = (Lead.objects.exclude(Email="steve@apple.com", LastName="Unittest General")
                 .filter(FirstName="User" + uid, LastName="Unittest General"))
        self.assertEqual(leads.count(), 1)

    def test_get(self) -> None:
        """Get the test lead record.
        """
        lead = Lead.objects.get(Email=test_email)
        self.assertEqual(lead.FirstName, 'User' + uid)
        self.assertEqual(lead.LastName, 'Unittest General')
        if not default_is_sf:
            self.skipTest("Default database should be any Salesforce.")
        # test a read only field (formula of full name)
        self.assertEqual(lead.Name, 'User%s Unittest General' % uid)

    def test_not_null(self) -> None:
        """Get the test lead record by isnull condition.
        """
        lead = Lead.objects.get(Email__isnull=False, FirstName='User' + uid)
        self.assertEqual(lead.FirstName, 'User' + uid)
        self.assertEqual(lead.LastName, 'Unittest General')

    def test_update(self) -> None:
        """Update the test lead record.
        """
        test_lead = Lead.objects.get(Email=test_email)
        self.assertEqual(test_lead.FirstName, 'User' + uid)
        test_lead.FirstName = 'Tested'
        test_lead.save()
        self.assertEqual(refresh(test_lead).FirstName, 'Tested')

    def test_save_update_fields(self) -> None:
        """Test the save method with parameter `update_fields`

        that updates only required fields.
        """
        company_orig = self.test_lead.Company
        self.test_lead.Company = 'nonsense'
        self.test_lead.FirstName = 'John'
        self.test_lead.save(update_fields=['FirstName'])
        test_lead = refresh(self.test_lead)
        self.assertEqual(test_lead.FirstName, 'John')
        self.assertEqual(test_lead.Company, company_orig)

    def test_query_all_deleted(self) -> None:
        """Test query for deleted objects (queryAll resource).
        """
        self.test_lead.delete()
        # TODO optimize counting because this can load thousands of records
        count_deleted = Lead.objects.db_manager(sf_alias).query_all(
                ).filter(IsDeleted=True, LastName="Unittest General").count()
        if not default_is_sf:
            self.skipTest("Default database should be any Salesforce.")
        self.assertGreaterEqual(count_deleted, 1)
        count_deleted2 = Lead.objects.filter(IsDeleted=True, LastName="Unittest General").query_all().count()
        self.assertGreaterEqual(count_deleted2, count_deleted)

        if DJANGO_22_PLUS:
            self.test_lead.pk = None
        self.test_lead.save()  # save anything again to be cleaned finally

    @skipUnless(default_is_sf, "Default database should be any Salesforce.")
    def test_generic_type_field(self) -> None:
        """Test that a generic foreign key can be filtered by type name and
        the type name can be referenced.
        """
        test_contact = Contact(first_name='sf_test', last_name='my')
        test_contact.save()
        note_1 = Note(title='note for Lead', parent_id=self.test_lead.pk)
        note_2 = Note(title='note for Contact', parent_id=test_contact.pk)
        note_1.save()
        note_2.save()
        try:
            self.assertEqual(Note.objects.filter(parent_type='Contact')[0].parent_type, 'Contact')
            self.assertEqual(Note.objects.filter(parent_type='Lead')[0].parent_type, 'Lead')

            note = Note.objects.filter(parent_type='Contact')[0]
            parent_model = getattr(salesforce.testrunner.example.models, note.parent_type)
            parent_object = parent_model.objects.get(pk=note.parent_id)
            self.assertEqual(parent_object.pk, note.parent_id)
        finally:
            note_1.delete()
            note_2.delete()
            test_contact.delete()


def clean_test_data() -> None:
    """Clean test objects after an interrupted test.

    All tests are written so that a failed test should not leave objects,
    but a test interrupted by debugger or Ctrl-C could do it.
    """
    ids = [x for x in Product.objects.filter(Name__startswith='test ')
           if re.match(r'test [a-z_0-9]+', x.Name)]
    Product.objects.filter(pk__in=ids).delete()
