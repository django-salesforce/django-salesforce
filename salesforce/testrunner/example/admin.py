"""
This is the python file that is responsible for the admin page layout. Go to /admin and log in for access
to the view.

@author Preston Mackert
"""

# -------------------------------------------------------------------------------------------------------------------- #
# Imports
# -------------------------------------------------------------------------------------------------------------------- #

from django.contrib import admin
from salesforce.testrunner.example import models
from salesforce.testrunner.example.universal_admin import register_omitted_classes


# -------------------------------------------------------------------------------------------------------------------- #
# Defining the layouts for the admin, uses a list_view type of style
# -------------------------------------------------------------------------------------------------------------------- #

class AccountAdmin(admin.ModelAdmin):
    list_display = ('Name', 'Phone')

class DocumentAdmin(admin.ModelAdmin):
    list_display = ('name', 'affiliate', 'any_information_identified')

class RegistrationAdmin(admin.ModelAdmin):
    list_display = ('name', 'eighteen_years_of_age')

class ProgramAdmin(admin.ModelAdmin):
    list_display = ('name', 'status')

class InsurancePlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'record_type_id')


# -------------------------------------------------------------------------------------------------------------------- #
# Registering object models to the admin site
# -------------------------------------------------------------------------------------------------------------------- #

admin.site.register(models.Account, AccountAdmin)
admin.site.register(models.Document, DocumentAdmin)
admin.site.register(models.Registration, RegistrationAdmin)
admin.site.register(models.Program, ProgramAdmin)
admin.site.register(models.InsurancePlan, InsurancePlanAdmin)

# call the custom django-salesforce universal , I've commented this out... my admin
# register_omitted_classes(models)
