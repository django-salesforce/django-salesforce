"""
Simple dynamic registration of admin for all yet unregistered models,
for demonstration, with respect to read only fields.
"""
from django.contrib import admin


def register_omitted_classes(models):
    """
    Register classes that don't have an own admin yet.
    Example:
        register_omitted_classes(some_app.models)
    """
    # This can be improved for fields that are only not creatable but are updateable or viceversa.
    for mdl in models.__dict__.values():
        if hasattr(mdl, '_salesforce_object') and not mdl._meta.abstract:
            attributes = {
                'readonly_fields':
                    [fld.name for fld in mdl._meta.fields if getattr(fld, 'sf_read_only', 0)]
            }
            list_display = [fld.name for fld in mdl._meta.fields if fld.column.lower() == 'name']
            if list_display:
                attributes['list_display'] = list_display
            try:
                admin.site.register(mdl,
                                    type(type(mdl).__name__ + 'Admin',
                                         (admin.ModelAdmin,),
                                         attributes)
                                    )
            except admin.sites.AlreadyRegistered:
                pass
