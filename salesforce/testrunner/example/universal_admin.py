"""
Simple dynamic registration of admin for all yet unregistered models,
for demonstration, with respect to read only fields.
"""
from django.contrib import admin
import salesforce

def register_omitted_classes(models):
	"""
	Register classes that don't have an own admin yet.
	Example:
		register_omitted_classes(some_app.models)
	"""
	# This can be improved for fields that are only not creatable but are updateable or viceversa.
	for mdl in models.__dict__.values():
		if hasattr(mdl, '_salesforce_object') and not mdl._meta.abstract:
			try:
				admin.site.register(
					mdl,
					type(
						type(mdl).__name__ + 'Admin',
						(admin.ModelAdmin,),
						{'readonly_fields': [mdl.name for mdl in mdl._meta.fields if getattr(mdl, 'sf_read_only', 0)]}
					)
				)
			except admin.sites.AlreadyRegistered:
				pass
