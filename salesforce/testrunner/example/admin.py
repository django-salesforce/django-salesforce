# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

from django.contrib import admin
#from django.db import models   # This name is overwritten by example.models below
from django.forms import widgets
from django.http import HttpResponse

from salesforce.testrunner.example import models
from salesforce.admin import RoutedModelAdmin
import salesforce

# This example is commented out in order to demonstrate capabilities of all models
class AccountAdmin(RoutedModelAdmin):
	#list_display = ('Salutation', 'Name', 'PersonEmail')
	list_display = ('Name', 'Phone')
admin.site.register(models.Account, AccountAdmin)

# Simple dynamic registration of all other models, with respect to read only fields.
# Can be improved for fields that are only not creatable but are updateable or viceversa.
for mdl in [x for x in models.__dict__.values() if hasattr(x, '_meta') and hasattr(x._meta, 'db_table') and not x._meta.abstract]:
	try:
		admin.site.register(mdl, type(type(mdl).__name__ + 'Admin', (RoutedModelAdmin,), {
			'readonly_fields': [x.name for x in mdl._meta.fields if getattr(x, 'sf_read_only', 0)]}))
	except admin.sites.AlreadyRegistered:
		pass
