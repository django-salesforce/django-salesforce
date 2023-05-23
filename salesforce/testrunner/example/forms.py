# django-salesforce
#
# by Hyneck Cernoch and Phil Christensen
# See LICENSE.md for details
#

from django import forms


class SearchForm(forms.Form):
    query = forms.CharField(max_length=100)
