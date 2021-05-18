"""
This is the python file that is responsible for the admin page layout. Go to /admin and log in for access
to the view.

@author Preston Mackert
"""

# -------------------------------------------------------------------------------------------------------------------- #
# Imports
# -------------------------------------------------------------------------------------------------------------------- #

from django.contrib import admin
from salesforce.testrunner.patient_connect import models
from salesforce.testrunner.patient_connect.universal_admin import register_omitted_classes


# -------------------------------------------------------------------------------------------------------------------- #
# Defining the layouts for the admin, uses a list_view type of style
# -------------------------------------------------------------------------------------------------------------------- #

class AccountAdmin(admin.ModelAdmin):
    list_display = ('Name', 'Phone')

class DocumentAdmin(admin.ModelAdmin):
    list_display = ('name', 'affiliate', 'document_type')

class RegistrationAdmin(admin.ModelAdmin):
    list_display = ('name', 'registration_type', 'hub_patient_id')

class ProgramAdmin(admin.ModelAdmin):
    list_display = ('name', 'status')

class InsurancePlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'record_type_id')

class SPStautsUpdateAdmin(admin.ModelAdmin):
    list_display = ('savings_card_id', 'brand_program', 'hub_patient_id')


# -------------------------------------------------------------------------------------------------------------------- #
# Registering object models to the admin site
# -------------------------------------------------------------------------------------------------------------------- #

admin.site.register(models.Account, AccountAdmin)
admin.site.register(models.Document, DocumentAdmin)
admin.site.register(models.Registration, RegistrationAdmin)
admin.site.register(models.Program, ProgramAdmin)
admin.site.register(models.InsurancePlan, InsurancePlanAdmin)
admin.site.register(models.SPStautsUpdate, SPStautsUpdateAdmin)

# call the custom django-salesforce universal , I've commented this out... my admin
# register_omitted_classes(models)
