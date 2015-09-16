# django-salesforce

"""
A set of tools to deal with Salesforce actions that
cannot or can hardly be implemented using the generic
relational database abstraction.

The Salesforce REST API is missing a few endpoints that
are available in the SOAP API. We are using `beatbox` as
a workaround for those specific actions (such as Lead-Contact
conversion).
"""

from django.conf import settings
from django.db import connections

try:
    import beatbox
except ImportError:
    beatbox = None


def convert_lead(lead, converted_status=None, **kwargs):
    """
    Convert `lead` using the `convertLead()` endpoint exposed
    by the SOAP API.

    The parameter `lead` is expected to be a Lead object that
    has not been converted yet.

	kwargs: additional optional parameters like `accountId` if the Lead should
		be merged with an existing Account. More info in
	https://developer.salesforce.com/docs/atlas.en-us.api.meta/api/sforce_api_calls_convertlead.htm

    -- BEWARE --
    The current implementation won't work in case your `Contact`,
    `Account` or `Opportunity` objects have some custom **and**
    required fields. This arises from the fact that `convertLead()`
    is only meant to deal with standard Salesforce fields, so it does
    not really care about populating custom fields at insert time.

    One workaround is to map a custom required field in
    your `Lead` object to every custom required field in the target
    objects (i.e., `Contact`, `Opportunity` or `Account`). Follow the
    instructions at

    https://help.salesforce.com/apex/HTViewHelpDoc?id=customize_mapleads.htm

    for more details.
    """
    if not beatbox:
        raise RuntimeError("To use convert_lead, you'll need to install the Beatbox library.")

    accepted_kw = set(('accountId', 'contactId', 'doNotCreateOpportunity',
                      'opportunityName', 'overwriteLeadSource', 'ownerId',
                      'sendNotificationEmail'))
    assert all(x in accepted_kw for x in kwargs)
    if converted_status is None:
        db_alias = lead._state.db
        converted_status = connections[db_alias].introspection.converted_lead_status
    soap_client = beatbox.PythonClient()
    settings_dict = settings.DATABASES['salesforce']

    # By default `beatbox` will assume we are trying to log in with a
    # production account (i.e., using login.salesforce.com). If we want
    # to use a sandbox, then we need to explicitly set the login url of
    # our `beatbox` client.
    if "test.salesforce.com" in settings_dict['HOST']:
        soap_client.serverUrl = 'https://test.salesforce.com/services/Soap/u/33.0'
    soap_client.login(settings_dict['USER'], settings_dict['PASSWORD'])

    kwargs['leadId'] = lead.pk
    kwargs['convertedStatus'] = converted_status
    response = soap_client.convertLead(kwargs)

    ret = dict((x._name[1], str(x)) for x in response)
    
    if "errors" in str(ret):
        raise RuntimeError("The Lead conversion failed: {0}, leadId={1}".format(
                ret['errors'], ret['leadId']))

    return ret
