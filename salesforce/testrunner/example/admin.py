# django-salesforce
#
# by Hyneck Cernoch and Phil Christensen
# See LICENSE.md for details
#

from django.contrib import admin
from salesforce.testrunner.example import models
from salesforce.testrunner.example.universal_admin import register_omitted_classes


class AccountAdmin(admin.ModelAdmin):
    # list_display = ('Salutation', 'Name', 'PersonEmail')
    list_display = ('Name', 'Phone')


admin.site.register(models.Account, AccountAdmin)

register_omitted_classes(models)
