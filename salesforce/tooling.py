"""
tooling - Tooling API Force.com

allows to create/read/update/delete code artifacts such as Apex Classes...
http://www.salesforce.com/us/developer/docs/api_tooling/         (HTML)
http://www.salesforce.com/us/developer/docs/api_tooling/api_tooling.pdf

It is the preferred API used by official SF tools: "Developer Console"
and the new version of "Force.com IDE".

I implemented a small part of it for people that like command line in Python.
My current module v0.3.* is experimental and can be much refactored before v0.4

Unimplemented:

Update of ApexClass is more complicated and I do not need it at all:
https://developer.salesforce.com/blogs/developer-relations/2013/01/new-in-spring-13-the-tooling-api.html

Many useful features (quick_search, create_trace_flag, run_tests_asynchronous,
run_tests_synchronous, run_test, describe_layout) can be found in the package 
SublimeApex (Force.com plugin for Sublime IDE, in Python, unknown license,
useful for inspiration)
https://github.com/xjsender/SublimeApex/blob/master/salesforce/api.py
"""

import re
from collections import namedtuple, OrderedDict
import datetime
import requests
import urllib
from django.db import connections
from salesforce import auth
from salesforce.backend.query import (API_STUB, SALESFORCE_DATETIME_FORMAT,
		handle_api_exceptions, sf_alias, urlencode, json)

__all__ = ('sf_query', 'sf_get', 'sf_post', 'sf_delete', 'sf_patch',
		'sf_get_text', 'get_all_names', 
		'set_trace_flag', 'execute_anonymous', 'execute_anonymous_logged',
		'install_metadata_service', 'call_metadata_api',
		'create_demo_test_object')
# TODO Test with international characters
# TODO Stabilize the API: basic functions, parameters...
#      to be easy usable now and
#      to be extensible, if necessary in the future

ApexExecutionResult_fields = (  # namedtuple('ApexExecutionResult',...)
		# standard Apex fields
		'line',                 # -1
		'column',               # -1
		'compiled',             # True
		'success',              # True
		'compileProblem',       # True
		'exceptionStackTrace',  # None
		'exceptionMessage'      # None
		# our fields
		'elapsed',    # datetime.timedelta  (days, seconds, microseconds)
		'timestamp'   # timestamp from SF server response (seconds resolution)
)

#class SF(object):

def sf_get_universal(cmd, using=sf_alias, **kwargs):
	"""
	Get information from SF REST API - universal format for internal use
	"""
	connection = connections[using]
	base = auth.authenticate(connection.settings_dict)['instance_url']
	if kwargs:
		cmd += '?' + urlencode(kwargs)
	url = u'{base}{api}/{cmd}'.format(base=base, api=API_STUB, cmd=cmd)
	return handle_api_exceptions(url, connection.sf_session.get)

def sf_get(cmd, using=sf_alias, **kwargs):
	"""
	Get information from SF REST API from JSON format.
	>>> data = sf_get('query', q='SELECT Count() FROM Lead')
	>>> number_of_leads = data['totalSize']
	"""
	response = sf_get_universal(cmd, using, **kwargs)
	data = response.json()
	data['elapsed'] = response.elapsed
	data['timestamp'] = datetime.datetime.strptime(response.headers['date'], '%a, %d %b %Y %H:%M:%S %Z')
	return data

def sf_get_text(cmd, using=sf_alias, **kwargs):
	"""
	Get information from SF REST API in TEXT format.
	"""
	response = sf_get_universal(cmd, using, **kwargs)
	return response.text

def sf_post(cmd, using=sf_alias, **kwargs):
	"""
	>>> response = sf_post('tooling/sobjects/ApexClass', name='Demo', body='public class Demo {\n}\n')
	>>> resp2 = sf_get('tooling/sobjects/ApexClass/{id}'.format(id=response.id))
	>>> assert 'public class Demo' in resp2.body
	>>> sf_delete('tooling/sobjects/ApexClass', response.id)
	"""
	connection = connections[using]
	base = auth.authenticate(connection.settings_dict)['instance_url']
	url = u'{base}{api}/{cmd}'.format(base=base, api=API_STUB, cmd=cmd)
	headers = {'Content-Type': 'application/json'}
	post_data = kwargs
	return handle_api_exceptions(url, connection.sf_session.post, headers=headers, data=json.dumps(post_data))

def sf_patch(cmd, using=sf_alias, **kwargs):
	connection = connections[using]
	base = auth.authenticate(connection.settings_dict)['instance_url']
	id = kwargs.pop('Id')
	url = u'{base}{api}/{cmd}/{id}'.format(base=base, api=API_STUB, cmd=cmd, id=id)
	headers = {'Content-Type': 'application/json'}
	post_data = kwargs
	return handle_api_exceptions(url, connection.sf_session.patch, headers=headers, data=json.dumps(post_data))

def sf_delete(cmd, pk, using=sf_alias):
	"""
	Delete by SF REST API
	"""
	connection = connections[using]
	base = auth.authenticate(connection.settings_dict)['instance_url']
	url = u'{base}{api}/{cmd}/{id}'.format(base=base, api=API_STUB, cmd=cmd, id=pk)
	return handle_api_exceptions(url, connection.sf_session.delete)

def sf_query(soql, is_tooling=False, using=sf_alias):
	match = re.match(r'select\s+\*\s+from\s+(\w+)', soql, flags=re.I)
	if match:
		sobject = match.groups()[0]
		fields = get_all_names(sobject, is_tooling, using=using)
		soql = soql.replace('*', ','.join(fields))
	prefix = 'tooling/' if is_tooling else ''
	# TODO Tooling does not use 'query_more' but Soql does.
	return sf_get(prefix + 'query', q=soql, using=sf_alias)


def execute_anonymous(apex_code, using=sf_alias):
	"""
	Run anonymous Apex code.

	>>> execute_anonymous("Contact contact = new Contact(LastName='test execute'); insert contact;")
	"""
	response = sf_get('tooling/executeAnonymous', anonymousBody=apex_code, using=using)
	data = OrderedDict.fromkeys(ApexExecutionResult_fields)
	data.update(response)
	return response

def execute_anonymous_logged(apex_code, using=sf_alias):
	"""
	Run anonymous Apex code with logging.

	The log can be very extensive and should be restricted by apropriate
	TraceFlag parameters:
	http://www.salesforce.com/us/developer/docs/api_tooling/Content/sforce_api_objects_traceflag.htm

	>>> result, log_info, log_body = execute_anonymous_logged("System.debug('Hello'+' World');")
	>>> assert 'Hello World' in log_body
	"""
	prev_start = sf_get('query', q="SELECT Max(StartTime) FROM ApexLog")['records'][0]['expr0']
	# execute apex code
	result = execute_anonymous(apex_code, using)
	# get the log
	operation = API_STUB + '/' + 'tooling/executeAnonymous'
	soql = ("SELECT Id, LastModifiedDate, SystemModstamp, LogUserId, "
			"Location, Application, Request, Operation, "
			"StartTime, DurationMilliseconds, LogLength, Status "
			"FROM ApexLog "
			"WHERE Operation='{operation}'".format(operation=operation)
			)
	sec = datetime.timedelta(seconds=1)
	if prev_start:
		soql += (" AND StartTime > {min_start} AND SystemModstamp <= {max_end}"
				.format(min_start=prev_start,
				max_end=datetime.datetime.strftime(result['timestamp'] + sec, SALESFORCE_DATETIME_FORMAT)
		))
	logs = sf_get('query', q=soql)
	print(result)
	print('prev: %s' % prev_start)
	print('logs: %s' % [x['StartTime'] for x in logs['records']])
	log_item, log_body = None, None
	if logs['records']:
		assert len(logs['records']) == 1
		log_item = logs['records'][0]
		log_body = sf_get_text('sobjects/ApexLog/{0}/Body'.format(log_item['Id']))
		print(log_item)
	return (result, log_item, log_body)

def set_trace_flag(traced_entity_id, scope_id, seconds=300, level=None, using=sf_alias, **kwargs):
	""" Creates or updates the FraceFlag records.

	The same level `level` is used for log categories that are not specified in kwargs)
	http://www.salesforce.com/us/developer/docs/api_tooling/Content/sforce_api_objects_traceflag.htm
	# minimal log only System.debug()
	>>> user_id = sf_get('')['identity'].split('/')[-1]
	>>> set_trace_flag(user_id, user_id, level='Debug', ApexProfiling='Warn', System='Warn')
	"""
	levels = "Finest Finer Fine Debug Info Warn Error".split()
	log_categories = "ApexCode ApexProfiling Callout Database System Validation VisualForce Workflow".split()
	soql = ("SELECT Id, ExpirationDate, {log_categories} "
			"FROM TraceFlag WHERE TracedEntityId='{traced_entity_id}' AND ScopeId='{scope_id}' "
			"LIMIT 1".format(
				log_categories=','.join(log_categories),
				traced_entity_id=traced_entity_id,
				scope_id=scope_id))
	ret = sf_query(soql, is_tooling=True, using=using)
	if ret['records']:
		trace_flag = ret['records'][0]
		print("original TraceFlag record:")
		print(trace_flag)
	else:
		trace_flag = {'TracedEntityId': traced_entity_id, 'ScopeId': scope_id}
	trace_flag['ExpirationDate'] = datetime.datetime.strftime(
			datetime.datetime.utcnow() + datetime.timedelta(seconds=seconds),
			SALESFORCE_DATETIME_FORMAT.replace('.%f', ''))
	if level is not None:
		trace_flag.update(dict.fromkeys(log_categories, level))
	trace_flag.update(kwargs)
	if 'Id' in trace_flag:
		sf_patch('tooling/sobjects/TraceFlag', using=using, **trace_flag)
	else:
		sf_post('tooling/sobjects/TraceFlag', using=using, **trace_flag)


def get_all_names(sobject, is_tooling=False, using=sf_alias):
	prefix = 'tooling/' if is_tooling else ''
	gdescribe = sf_get('{prefix}sobjects/{sobject}/describe'.format(
			prefix=prefix, sobject=sobject), using=using)
	return [str(x['name']) for x in gdescribe['fields']]

#def query_all_fields(sobject, where=None, is_tooling=False, using=sf_alias):
#	prefix = 'tooling/' if is_tooling else ''
#	where = ('where ' + where) if where else ''
#	fields = ', '.join(get_all_names(sobject, is_tooling, using=using))
#	result = sf_get(
#			'{prefix}query'.format(prefix=prefix), 
#			q="select {fields} from {sobject} {where}".format(fields=fields,
#				sobject=sobject, where=where),
#			using=using)
#	return result

# Important fields of 'tooling/TraceFlag' are 'ScopeId', 'TracedEntityId' 



# --- Metadata API ---

# copied from the blog by Anderew Fawcett
# http://andyinthecloud.com/2014/04/24/apex-metadata-api-and-spring14-keys-to-the-kingdom/
# http://andyinthecloud.com/2013/10/27/introduction-to-calling-the-metadata-api-from-apex/

# This implementation of Metadate API requires enabled callouts to your SF site.

def install_metadata_service():
	"""
	Installs an wrapper `MetadataService.cls` to Salesforce
	
	for use Metadata API from Apex.
	Can be installed without callouts, but then are callouts necessary
	"""
	name = 'MetadataService'
	pattern = 'https://github.com/financialforcedev/apex-mdapi/raw/master/apex-mdapi/src/classes/{0}.cls'
	response = sf_get('tooling/query', q="select Name from ApexClass where Name='{0}'".format(name))
	if not response['records']:
		source = requests.get(pattern.format(name)).text
		response = sf_post('tooling/sobjects/ApexClass', name=name, body=source)

def call_metadata_api(apex_code):
	"""
	Call Metadata API with an Apex code.

	Only synchronous CRUD-based calls are supported.
	More Metadata of the same type can be used in one call to createMetadata,
	but not CustomObject and CustomField together.
	http://www.salesforce.com/us/developer/docs/api_meta/Content/meta_crud_based_calls_intro.htm

	See `create_demo_test_object` function for an example.
	"""
	# universal common code for synchronous CRUD-based calls
	common_apex_code = """
	public class MetadataServiceException extends Exception { }

	public void handleSaveResults(List<MetadataService.SaveResult> saveResults) {
		for(MetadataService.SaveResult saveResult : saveResults) {
			if(saveResult==null || saveResult.success)
				continue;
			List<String> messages = new List<String>();
			messages.add('Errors in ' + saveResult.fullName);
			for(MetadataService.Error error : saveResult.errors)
				messages.add(
				error.message + ' (' + error.statusCode + ').' +
				( error.fields!=null && error.fields.size()>0 ?
				' Fields ' + String.join(error.fields, ',') + '.' : '' ) );
			if(messages.size()>0)
				throw new MetadataServiceException(String.join(messages, '; '));
		}
	}

	MetadataService.MetadataPort service = new MetadataService.MetadataPort();
	service.SessionHeader = new MetadataService.SessionHeader_element();
	service.SessionHeader.sessionId = UserInfo.getSessionId();
	"""
	apex_code = apex_code or demo_apex_code
	resp = execute_anonymous(common_apex_code + apex_code)
	if not resp['success']:
		err_pattern = (r'System.CalloutException: IO Exception: Unauthorized endpoint.*'
				r'endpoint = (https://\w+.salesforce.com)/')
		match = re.match(err_pattern, resp['exceptionMessage'] or '')
		if match:
			# Solution with callouts is easier than with SOAP in Python
			# also because example code is available only for Java.
			site = match.groups()[0]
			print("Error: Metadata can not be changed without enabled callouts (by this method).\n"
				'Callouts can be enabled manually by:\n'
				'  Setup => Administration Setup => Security Controls => Remote Site Settings\n'
				'    Remote Site Name: e.g. "sf_soap_api"\n'
				'    Remote Site URL:  "{site}"\n'.format(site=site))
			# Callouts to SF can be disabled manually again after db structure deployment.
		else:
			print("Error: " + (resp['exceptionMessage'] if resp['compiled'] else resp['compileProblem']))
	return resp


def create_demo_test_object():
	"""
	Creates an object `Test__c` with the name field `Test Record` and the text field `Test__c`.

	More Metadata of the same type in the list can be used in one call to
	createMetadata, but not together e.g. CustomObject and CustomField.
	"""
	# This can be used internally if syncan example output of `manage.py sqlall`
	demo_apex_code = """ 
	MetadataService.CustomObject customObject = new MetadataService.CustomObject();
	String objectName = 'Test';
	customObject.fullName = objectName + '__c';
	customObject.label = objectName;
	customObject.pluralLabel = objectName+'s';
	customObject.nameField = new MetadataService.CustomField();
	customObject.nameField.type_x = 'Text';
	customObject.nameField.label = 'Test Record';
	customObject.deploymentStatus = 'Deployed';
	customObject.sharingModel = 'ReadWrite';
	handleSaveResults(service.createMetadata(new List<MetadataService.Metadata> { customObject }));

	MetadataService.CustomField customField = new MetadataService.CustomField();
	customField.fullName = 'Test__c.TestField__c';
	customField.label = 'Test Field';
	customField.type_x = 'Text';
	customField.length = 42;
	handleSaveResults(service.createMetadata(new List<MetadataService.Metadata> { customField }));
	"""
	call_metadata_api(demo_apex_code)
