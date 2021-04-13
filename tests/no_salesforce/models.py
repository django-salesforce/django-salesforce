"""
Backward compatible behaviour with a primary key 'Id' and upper-case field names

"""

from django.db import models


class User(models.Model):
    username = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    first_name = models.CharField(max_length=40, null=True, blank=True)
    email = models.EmailField()
    is_active = models.BooleanField(default=False)


class Lead(models.Model):
    company = models.CharField(max_length=255)
    last_name = models.CharField(max_length=80)
    owner = models.ForeignKey(User, on_delete=models.DO_NOTHING)
