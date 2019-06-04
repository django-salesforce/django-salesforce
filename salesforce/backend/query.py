# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

"""
Salesforce object query and queryset customizations.  (like django.db.models.query)
"""
import warnings

from django.db import NotSupportedError
from django.db.models import query
from salesforce.backend.indep import get_sf_alt_pk

from salesforce.backend import DJANGO_20_PLUS
from salesforce.router import is_sf_database


# class SalesforceRawQuerySet(query.RawQuerySet):
#     def __len__(self):
#         if self.query.cursor is None:
#             # force the query
#             self.query.get_columns()
#         return self.query.cursor.rowcount


class SalesforceQuerySet(query.QuerySet):
    """
    Use a custom SQL compiler to generate SOQL-compliant queries.
    """

    def query_all(self):
        """
        Allows querying for also deleted or merged records.
            Lead.objects.query_all().filter(IsDeleted=True,...)
        https://www.salesforce.com/us/developer/docs/api_rest/Content/resources_queryall.htm
        """
        if DJANGO_20_PLUS:
            obj = self._clone()
        else:
            obj = self._clone(klass=SalesforceQuerySet)  # pylint: disable=unexpected-keyword-arg
        obj.query.set_query_all()
        return obj

    def simple_select_related(self, *fields):
        if DJANGO_20_PLUS:
            raise NotSupportedError("Obsoleted method .simple_select_related(), use .select_related() instead")
        warnings.warn("Obsoleted method .simple_select_related(), use .select_related() instead")
        return self.select_related(*fields)

    def bulk_create(self, objs, batch_size=None, ignore_conflicts=False, **kwargs):
        # pylint:disable=arguments-differ,unused-argument
        # parameter 'ignore_conflicts=False' is new in Django 2.2
        if getattr(self.model, '_salesforce_object', '') == 'extended' and not is_sf_database(self.db):
            objs = list(objs)
            for x in objs:
                if x.pk is None:
                    x.pk = get_sf_alt_pk()
        return super(SalesforceQuerySet, self).bulk_create(objs, batch_size=batch_size, **kwargs)
