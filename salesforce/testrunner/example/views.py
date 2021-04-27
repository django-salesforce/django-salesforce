"""
custom views that leverage our salesforce data!

@author Preston Mackert
"""

# -------------------------------------------------------------------------------------------------------------------- #
# imports
# -------------------------------------------------------------------------------------------------------------------- #

import logging
from django import shortcuts
from salesforce.testrunner.example import models, forms

log = logging.getLogger(__name__)


# -------------------------------------------------------------------------------------------------------------------- #
# call the code for different views
# -------------------------------------------------------------------------------------------------------------------- #

def list_accounts(request):
    accounts = models.Account.objects.all()[0:5]

    return shortcuts.render(request, 'list-accounts.html',
                            dict(title="List First 5 Accounts", accounts=accounts)
                            )


def search_accounts(request):
    accounts = []
    if request.method == 'POST':
        form = forms.SearchForm(request.POST)
        if form.is_valid():
            accounts = models.Account.objects.filter(Name__icontains=form.cleaned_data['query'])
    else:
        form = forms.SearchForm()

    return shortcuts.render(request, 'search-accounts.html',
                            dict(title="Search Accounts by Email", accounts=accounts, form=form)
                            )


# -------------------------------------------------------------------------------------------------------------------- #
# sp portal 
# -------------------------------------------------------------------------------------------------------------------- #

def sp_portal(request):
    documents = models.Document.objects.all()

    return shortcuts.render(request, 'sp-portal.html', 
                            dict(title="sp portal docs", documents=documents)
                            )

