# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

"""
Multi-database support for the Django admin.
Not important yet - replaced by an empty stub.
"""
from django.contrib.admin.options import ModelAdmin as RoutedModelAdmin

#from django.contrib.admin import options
#from django.conf import settings
#from django.db import utils
#from salesforce import DJANGO_17_PLUS
#
#class RoutedModelAdmin(options.ModelAdmin):
#	"""
#	ModelAdmin subclass that allows use of multiple database connections.
#	
#	To use the Django admin with Salesforce models, you'll need at least two databases,
#	unless you somehow were to save all the django_session and assorted tables in SF.
#	
#	Unfortunately, at least as far as Django 1.3 or 1.7, the admin doesn't normally make use
#	of the DATABASE_ROUTERS setting, so this custom ModelAdmin subclass makes up for it.
#	"""
#	# TODO This class can be simplified now, without Django 1.3
#	router = utils.ConnectionRouter(settings.DATABASE_ROUTERS)
#	
#	def save_model(self, request, obj, form, change):
#		# Tell Django to save objects to the 'other' database.
#		obj.save(using=self.router.db_for_write(obj))
#
#	def delete_model(self, request, obj):
#		# Tell Django to delete objects from the 'other' database
#		obj.delete(using=self.router.db_for_write(obj))
#
#	def queryset(self, request):
#		qs = self.model.objects.get_query_set()
#		qs.using(self.router.db_for_read(self.model))
#		# TODO: this should be handled by some parameter to the ChangeList.
#		ordering = self.ordering or () # otherwise we might try to *None, which is bad ;)
#		if ordering:
#			qs = qs.order_by(*ordering)
#		return qs
#
#	if DJANGO_17_PLUS:
#		get_queryset = queryset
#		del queryset
#
#	def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
#		# Tell Django to populate ForeignKey widgets using a query
#		# on the 'other' database.
#		return super(RoutedModelAdmin, self).formfield_for_foreignkey(db_field, request=request, using=self.router.db_for_read(self.model), **kwargs)
#
#	def formfield_for_manytomany(self, db_field, request=None, **kwargs):
#		# Tell Django to populate ManyToMany widgets using a query
#		# on the 'other' database.
#		return super(RoutedModelAdmin, self).formfield_for_manytomany(db_field, request=request, using=self.router.db_for_read(self.model), **kwargs)
