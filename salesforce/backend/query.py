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

from salesforce.backend import DJANGO_20_PLUS


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

    def iterator(self, chunk_size=2000):
        """
        An iterator over the results from applying this QuerySet to the
        database.
        """
        return iter(self._iterable_class(self))

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
