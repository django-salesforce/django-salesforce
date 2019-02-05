# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

"""
Salesforce object query and queryset customizations.  (like django.db.models.query)
"""

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
        """
        Simplified "select_related" for Salesforce

        Example:
            for x in Contact.objects.filter(...).order_by('id')[10:20].simple_select_related('account'):
                print(x.name, x.account.name)
        Restrictions:
            * This must be the last method in the queryset method chain, after every other
              method, after a possible slice etc. as you see above.
            * Fields must be explicitely specified. Universal caching of all related
              without arguments is not implemented (because it could be inefficient and
              complicated if some of them should be deferred)
        """
        if not fields:
            raise Exception("Fields must be specified in 'simple_select_related' call, otherwise it wol")
        for rel_field in fields:
            rel_model = self.model._meta.get_field(rel_field).related_model
            rel_attr = self.model._meta.get_field(rel_field).attname
            rel_qs = rel_model.objects.filter(pk__in=self.values_list(rel_attr, flat=True))
            fk_map = {x.pk: x for x in rel_qs}
            for x in self:
                rel_fk = getattr(x, rel_attr)
                if rel_fk:
                    setattr(x, '_{}_cache'.format(rel_field), fk_map[rel_fk])
        return self
