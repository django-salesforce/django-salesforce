"""
custom views that leverage our salesforce data!

@author Preston Mackert
"""

# -------------------------------------------------------------------------------------------------------------------- #
# imports
# -------------------------------------------------------------------------------------------------------------------- #

import logging
from django import shortcuts
from salesforce.testrunner.patient_connect import models, forms

log = logging.getLogger(__name__)


# -------------------------------------------------------------------------------------------------------------------- #
# our index view, when you open the app
# -------------------------------------------------------------------------------------------------------------------- #

def index(request):
    return shortcuts.render(request, 'patient_connect/index.html',
                            dict(title="Lilly Patient Services")
                            )


# -------------------------------------------------------------------------------------------------------------------- #
# sp portal automation
# -------------------------------------------------------------------------------------------------------------------- #

def list_specialty_pharmacy_status(request):
    updates = models.SPStautsUpdate.objects.all()

    return shortcuts.render(request, 'patient_connect/list-specialty-pharmacy-status.html',
                            dict(title="List SP Status Updates", updates=updates)
                            )


def search_sp_updates(request):
    updates = []
    if request.method == 'POST':
        form = forms.SearchForm(request.POST)
        if form.is_valid():
            updates = models.SPStautsUpdate.objects.filter(hub_patient_id__icontains=form.cleaned_data['query'])
    else:
        form = forms.SearchForm()

    return shortcuts.render(request, 'patient_connect/search-sp-updates.html',
                            dict(title="Search SP Updates", updates=updates, form=form)
                            )