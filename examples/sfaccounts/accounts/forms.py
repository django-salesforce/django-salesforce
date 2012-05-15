# django-salesforce
#
# by Phil Christensen
# (c) 2012 Working Today
# See LICENSE.md for details
#

from django import forms

class SearchForm(forms.Form):
	query = forms.CharField(max_length=100)
