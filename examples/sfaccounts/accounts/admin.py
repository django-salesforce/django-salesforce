from django.contrib import admin
from django.db import models
from django.forms import widgets
from django.http import HttpResponse

from salesforce import models
from salesforce.admin import RoutedModelAdmin

class AccountAdmin(RoutedModelAdmin):
	pass

admin.site.register(models.Account, AccountAdmin)
