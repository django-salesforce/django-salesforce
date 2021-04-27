from django.contrib import admin

from . import models


class SFTPUserGroupAdmin(admin.ModelAdmin):
    """Admin class for SFTPUserGroup
    """
    list_display = ('name',)
    search_fields = ('name',)


class SFTPUserAccountAdmin(admin.ModelAdmin):
    """Admin class for SFTPUserAccountAdmin
    """
    list_display = ('user', 'group', 'last_login')
    search_fields = ('user', 'group', 'last_login')


admin.site.register(models.SFTPUserGroup, SFTPUserGroupAdmin)
admin.site.register(models.SFTPUserAccount, SFTPUserAccountAdmin)
