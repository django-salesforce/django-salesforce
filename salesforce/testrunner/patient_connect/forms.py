# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

from django import forms


class SearchForm(forms.Form):
    query = forms.CharField(max_length=100)
