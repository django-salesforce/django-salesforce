# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

"""
Salesforce object manager. (like django.db.models.manager)

Use a custom QuerySet to generate SOQL queries and results.
"""

from django.conf import settings
from django.db.models import manager
from django.db.utils import DEFAULT_DB_ALIAS

from salesforce import router
from salesforce.backend import query, models_sql_query, compiler, DJANGO_20_PLUS


class SalesforceManager(manager.Manager):
    if not DJANGO_20_PLUS:
        use_for_related_fields = True
        silence_use_for_related_fields_deprecation = True  # pylint:disable=invalid-name  # name from Django

    def get_queryset(self, _alias=None):
        """
        Returns a QuerySet which access remote SF objects.
        """
        alias_is_sf = _alias and router.is_sf_database(_alias)
        extended_model = getattr(self.model, '_salesforce_object', '') == 'extended'
        if router.is_sf_database(self.db) or alias_is_sf or extended_model:
            q = models_sql_query.SalesforceQuery(self.model, where=compiler.SalesforceWhereNode)
            return query.SalesforceQuerySet(self.model, query=q, using=self.db)
        return super(SalesforceManager, self).get_queryset()

    def using(self, alias):
        if alias is None:
            if hasattr(self.model, '_salesforce_object'):
                alias = getattr(settings, 'SALESFORCE_DB_ALIAS', 'salesforce')
            else:
                alias = DEFAULT_DB_ALIAS
        if router.is_sf_database(alias, self.model):
            return self.get_queryset(_alias=alias).using(alias)
        return super(SalesforceManager, self).using(alias)

    # def raw(self, raw_query, params=None, translations=None):
    #     if router.is_sf_database(self.db):
    #         q = models_sql_query.SalesforceRawQuery(raw_query, self.db, params)
    #         return query.SalesforceRawQuerySet(raw_query=raw_query, model=self.model, query=q,
    #                                            params=params, using=self.db)
    #     return super(SalesforceManager, self).raw(raw_query, params=params, translations=translations)

    def query_all(self):
        if router.is_sf_database(self.db):
            return self.get_queryset().query_all()
        return self.get_queryset()
