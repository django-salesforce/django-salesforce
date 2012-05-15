# django-salesforce
#
# by Phil Christensen
# (c) 2012 Working Today
# See LICENSE.md for details
#

from django.contrib.admin import options
from django.conf import settings
from django.db import utils

class RoutedModelAdmin(options.ModelAdmin):
	router = utils.ConnectionRouter(settings.DATABASE_ROUTERS)
	
	def save_model(self, request, obj, form, change):
		# Tell Django to save objects to the 'other' database.
		obj.save(using=self.router.db_for_write(obj))

	def delete_model(self, request, obj):
		# Tell Django to delete objects from the 'other' database
		obj.delete(using=self.router.db_for_write(obj))

	def queryset(self, request):
		qs = self.model.objects.get_query_set()
		qs.using(self.router.db_for_read(self.model))
		# TODO: this should be handled by some parameter to the ChangeList.
		ordering = self.ordering or () # otherwise we might try to *None, which is bad ;)
		if ordering:
			qs = qs.order_by(*ordering)
		return qs

	def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
		# Tell Django to populate ForeignKey widgets using a query
		# on the 'other' database.
		return super(RoutedModelAdmin, self).formfield_for_foreignkey(db_field, request=request, using=self.router.db_for_read(self.model), **kwargs)

	def formfield_for_manytomany(self, db_field, request=None, **kwargs):
		# Tell Django to populate ManyToMany widgets using a query
		# on the 'other' database.
		return super(RoutedModelAdmin, self).formfield_for_manytomany(db_field, request=request, using=self.router.db_for_read(self.model), **kwargs)
