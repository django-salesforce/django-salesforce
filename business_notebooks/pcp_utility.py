# ------------------------------- #
# imports 
# ------------------------------- #

import os
from simple_salesforce import Salesforce



# -------------------------------------------------------------------------------------------------------------------- #
# environment connections
# -------------------------------------------------------------------------------------------------------------------- #

def connect_to_prod(use_proxies):
    """ proxies give us elevated security during our connections sessions """
    # defining our log in credentials, saved as environment variables
    username = os.environ.get('FORCE_PROD_USER')
    password = os.environ.get('FORCE_PROD_PW')
    security_token = os.environ.get('FORCE_PROD_TOKEN')
    if use_proxies:
        proxies = {
            'http': 'http://preston:mackert@us_proxy_indy.xh1.lilly.com:9000',
            'https': 'http://preston:mackert@us_proxy_indy.xh1.lilly.com:9000'
        }

        sf = Salesforce(username=username, password=password, security_token=security_token, proxies=proxies)
    else:
        sf = Salesforce(username=username, password=password, security_token=security_token)
    return sf


# -------------------------------------------------------------------------------------------------------------------- #
# query utilities
# -------------------------------------------------------------------------------------------------------------------- #

def query(sf, soql):
    # uses query_all so results are not paginated...
    soql_query = sf.query_all(soql)
    
    size = soql_query['totalSize']
    done = soql_query['done']
    # records are the actual data returned inside of the function's json
    records = soql_query['records']
    """ i am reformatting the return result so that this custom function just gives a clean python list """
    returned_records = []
    for record in records:
        record_fields = {}
        attributes = record['attributes']
        for key in record.keys():
            if record[key] != attributes:
                record_fields[key] = record[key]
        returned_records.append(record_fields)
    # cleaned python list of records, each record will have JSON to hold data
    return returned_records


def query_list(sf, soql, the_list):
    """ when using the IN operator, if the list contains more than 20k characters, it hits a limit so partition it, I
    used 700 as a partition length for a safe number, but feel free to improve :) """
    records = []
    number_of_lists = round(len(the_list) / 700)
    if number_of_lists == 0:
        number_of_lists = 1
    start_index = 0
    try:
        partition_length = round(len(the_list) / number_of_lists)
    except:
        partition_length = round(len(the_list))
    end_index = partition_length
    for i in range(number_of_lists):
        sub_list = the_list[start_index:end_index]
        list_string = format_list(sub_list)
        sub_soql = soql + "%s" % list_string
        try:
            sf_data = query(sf, sub_soql)
        # broad exception... didn't figure out all the different errors we might get here...
        except:
            sf_data = []
            print("SOQL error, no data returned")
        for record in sf_data:
            records.append(record)
        start_index = end_index
        end_index = partition_length * (i + 2)
    # returning all the records found in the query
    return records


# -------------------------------------------------------------------------------------------------------------------- #
# consent parsing
# -------------------------------------------------------------------------------------------------------------------- #

def parse_consents(program):
    """ consents are processed upon patient enrollment into a CSP and stored to either a patient/caregiver through
     the program record """
    try:
        consents = program['Consent_Auth_Preferences__r']['records']
        consent_data = []
        for record in consents:
            consent_record = {}
            for key in record:
                if key != 'attributes':
                    consent_record[key] = record[key]
            consent_data.append(consent_record)
    except KeyError:
        consent_data = []

    # return a list of all the consent records cleaned up
    return consent_data


# -------------------------------------------------------------------------------------------------------------------- #
# coverage parsing
# -------------------------------------------------------------------------------------------------------------------- #

def parse_coverages(program):
    """ takes in a program and returns a list containing a list of copay coverages and a list of insurance coverages """
    try:
        # store copay records in first list, insurance records in the second list
        coverage_data = [[], []]
        coverages = program['Coverage1__r']['records']
        for record in coverages:
            try:
                if record['RecordTypeId'] == '012f20000001HL3AAM':
                    copay_coverage_record = {}
                    for key in record:
                        if key != 'attributes' and key != 'RecordTypeId':
                            copay_coverage_record[key] = record[key]
                    coverage_data[0].append(copay_coverage_record)

                elif record['RecordTypeId'] == '012f20000001HL4AAM':
                    insurance_coverage_record = {}
                    for key in record:
                        if key != 'attributes' and key != 'RecordTypeId':
                            insurance_coverage_record[key] = record[key]
                    coverage_data[1].append(insurance_coverage_record)

            except KeyError:
                print("queries that incorporate coverage records must include the RecordTypeId field")

    # return an empty data model if we pass the method an invalid data structure
    except KeyError:
        coverage_data = [[], []]
    return coverage_data


def filter_active_coverages(coverages):
    """ takes a list of coverage records and parses out any inactive records (good for separating ins and copay) """
    active_coverages = []
    for coverage in coverages:
        try:
            if coverage['DTPC_Record_Status__c'] == 'Active':
                active_coverages.append(coverage)
        except KeyError:
            print("this method requires you to pull the DTPC_Record_Status__c from coverage")
    return active_coverages


def parse_old_coverages(program):
    try:
        # store copay records in first list, insurance records in the second list
        coverage_data = []
        coverages = program['Coverage__r']['records']
        for record in coverages:
            old_coverage_record = {}
            for key in record:
                if key != 'attributes':
                    old_coverage_record[key] = record[key]
            coverage_data.append(old_coverage_record)
    # return an empty data model if we pass the method an invalid data structure
    except KeyError:
        coverage_data = []
    return coverage_data


def filter_active_old_coverages(coverages):
    active_coverages = []
    for coverage in coverages:
        try:
            if coverage['Coverage_Status__c'] == 'Active':
                active_coverages.append(coverage)
        except KeyError:
            print("this method requires your query to pull the Coverage_Status__c field from coverage")
    return active_coverages


# -------------------------------------------------------------------------------------------------------------------- #
# claims parsing
# -------------------------------------------------------------------------------------------------------------------- #

def parse_claims(program):
    try:
        claims = program['Claims_Adjudication__r']['records']
        claims_data = []
        for record in claims:
            claim_record = {}
            for key in record:
                if key !='attributes':
                    claim_record[key] = record[key]
            claims_data.append(claim_record)
    except KeyError:
        claims_data = []

    return claims_data


# -------------------------------------------------------------------------------------------------------------------- #
# dispense parsing
# -------------------------------------------------------------------------------------------------------------------- #

def parse_dispenses(program):
    try:
        dispenses = program['Specialty_Pharmacy_Dispenses__r']['records']
        dispense_data = []
        for record in dispenses:
            dispense_record = {}
            for key in record:
                if key != 'attributes':
                    dispense_record[key] = record[key]
            dispense_data.append(dispense_record)
    except KeyError:
        dispense_data = []

    return dispense_data


# -------------------------------------------------------------------------------------------------------------------- #
# program services parsing
# -------------------------------------------------------------------------------------------------------------------- #

def parse_program_services(program):
    try:
        services = program['Program_Services__r']['records']
        services_data = []
        for record in services:
            service_record = {}
            for key in record:
                if key != 'attributes':
                    service_record[key] = record[key]
            services_data.append(service_record)
    except KeyError:
        services_data = []

    return services_data


# -------------------------------------------------------------------------------------------------------------------- #
# agent workflow parsing
# -------------------------------------------------------------------------------------------------------------------- #

def parse_cases(program):
    try:
        cases = program['Cases__r']['records']
        case_data = []
        for record in cases:
            case_record = {}
            for key in record:
                if key != 'attributes':
                    case_record[key] = record[key]
            case_data.append(case_record)
    except KeyError:
        case_data = []

    return case_data


def parse_document_logs(program):
    logs = program['Document_Logs__r']
    try:
        document_logs = logs['records']
        document_data = []
        for record in document_logs:
            document_record = {}
            for key in record:
                if key != 'attributes':
                    document_record[key] = record[key]
            document_data.append(document_record)

    except KeyError:
        document_data = []

    # return the two separate data structures
    return document_data
