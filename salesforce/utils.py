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

from django.db import connections

import salesforce
from salesforce.dbapi.driver import beatbox, DatabaseError, InterfaceError


def get_soap_client(db_alias, client_class=None):
    """
    Create the SOAP client for the current user logged in the db_alias

    The default created client is "beatbox.PythonClient", but an
    alternative client is possible. (i.e. other subtype of beatbox.XMLClient)
    """
    if not beatbox:
        raise InterfaceError("To use SOAP API, you'll need to install the Beatbox package.")
    if client_class is None:
        client_class = beatbox.PythonClient
    soap_client = client_class()

    # authenticate
    connection = connections[db_alias]
    # verify the authenticated connection, because Beatbox can not refresh the token
    cursor = connection.cursor()
    cursor.urls_request()
    auth_info = connections[db_alias].sf_session.auth

    access_token = auth_info.get_auth()['access_token']
    assert access_token[15] == '!'
    org_id = access_token[:15]
    url = '/services/Soap/u/{version}/{org_id}'.format(version=salesforce.API_VERSION,
                                                       org_id=org_id)
    soap_client.useSession(access_token, auth_info.instance_url + url)
    return soap_client


def convert_lead(lead, converted_status=None, **kwargs):
    """
    Convert `lead` using the `convertLead()` endpoint exposed
    by the SOAP API.

    Parameters:
    `lead` -- a Lead object that has not been converted yet.
    `converted_status` -- valid LeadStatus value for a converted lead.
        Not necessary if only one converted status is configured for Leads.

    kwargs: additional optional parameters according docs
    https://developer.salesforce.com/docs/atlas.en-us.api.meta/api/sforce_api_calls_convertlead.htm
    e.g. `accountId` if the Lead should be merged with an existing Account.

    Return value:
        {'accountId':.., 'contactId':.., 'leadId':.., 'opportunityId':.., 'success':..}

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
    # pylint:disable=protected-access
    if not beatbox:
        raise InterfaceError("To use convert_lead, you'll need to install the Beatbox library.")

    accepted_kw = set(('accountId', 'contactId', 'doNotCreateOpportunity',
                       'opportunityName', 'overwriteLeadSource', 'ownerId',
                       'sendNotificationEmail'))
    assert all(x in accepted_kw for x in kwargs)

    db_alias = lead._state.db
    if converted_status is None:
        converted_status = connections[db_alias].introspection.converted_lead_status
    soap_client = get_soap_client(db_alias)

    # convert
    kwargs['leadId'] = lead.pk
    kwargs['convertedStatus'] = converted_status
    response = soap_client.convertLead(kwargs)

    ret = dict((x._name[1], str(x)) for x in response)

    if "errors" in str(ret):
        raise DatabaseError("The Lead conversion failed: {0}, leadId={1}"
                            .format(ret['errors'], ret['leadId']))
    return ret
