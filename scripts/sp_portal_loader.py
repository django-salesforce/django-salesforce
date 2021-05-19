"""
creating a file that allows us to load records into the environment... this is going
to be used to try and create test docs to start

Good Extension!!! -- https://django-extensions.readthedocs.io/en/latest/runscript.html

@author Preston Mackert
"""

# -------------------------------------------------------------------------------------------------------------------- #
# imports
# -------------------------------------------------------------------------------------------------------------------- #

import logging
from django import shortcuts
from datetime import datetime
from salesforce.testrunner.patient_connect import models


# -------------------------------------------------------------------------------------------------------------------- #
# sp portal document feed
# -------------------------------------------------------------------------------------------------------------------- #

# ToDo: implement a test_file loader, setup Django sFTP in order to route test files and production files to different folders...
def load_sp_pipe_file(filename):
    """ loading in a handmade test file... pipe deliniated is annoying, but hey, this works """
    # open file, read lines and clean
    file_handler = open(filename, 'r')
    clean_lines = []
    for line in file_handler:
        line_vector = line.rstrip().split('|')
        if len(line_vector) > 1:
            clean_lines.append(line_vector)

    # put each unique status update in a record format (can compare and search sfdc now...)
    status_updates = []
    headers = clean_lines[0]
    index = 0
    for line in clean_lines[1:]:
        status_update = {}
        for header in headers:
            if header == "ï»¿Brand_Program":
                header = "Brand_Program"
            status_update[header] = line[index]
            index += 1
        status_updates.append(status_update)
        index = 0

    # close out the file handler... this file should be on a server
    file_handler.close()
    return status_updates


def create_records(status_updates):
    """ 
    function to actually create the records in the pcp...

    THIS IS THE FIA
    -------------------------
    
    Brand_Program
    Hub_Patient_ID
    Savings_Card_ID

    NPI_DEA
    HCP_First_Name
    HCP_Last_Name
    HCP_Address1
    HCP_Address2
    HCP_City
    HCP_State
    HCP_Zip
    HCP_Phone
    
    Payer_Name
    Plan_Name
    Insurance_BIN
    Insurance_PCN
    Insurance_Group
    Insurance_ID
    Insurance_Phone
    
    Pharmacy_Name
    Added_HUB_Patient_ID
    
    PA_FE_Submitted
    PA_FE_Submitted_Date
    PA_FE_Status
    PA_FE_Denial_Reason
    Appeal_Submitted
    Appeal_Status
    Appeal_Denial_Reason
    ME -- oncology matters
    ME_Submitted_Date
    ME_Status
    ME_Denial_Reason
    PA_NA
    
    ON_Label
    
    Transfer
    
    Group_Number
    IQVIA_BIN
    IQVIA_PCN
    """
    new_updates = []
    errored_updates = []
    for status_update in status_updates:
        """ load key, value pair into salesforce """
        try:
            # general program data
            brand_program = status_update['Brand_Program']
            hub_patient_id = status_update['Hub_Patient_ID']
            savings_card_id = status_update['Savings_Card_ID']
            
            # physician information
            npi_dea = status_update['NPI_DEA']
            hcp_first_name = status_update['HCP_First_Name']
            hcp_last_name = status_update['HCP_Last_Name']
            hcp_address1 = status_update['HCP_Address1']
            hcp_address2 = status_update['HCP_Address2']
            hcp_city = status_update['HCP_City']
            hcp_state = status_update['HCP_State']
            hcp_zip = status_update['HCP_Zip']
            hcp_phone = status_update['HCP_Phone']

            # insurance information
            payer_name = status_update['Payer_Name']
            plan_name = status_update['Plan_Name']
            insurance_bin = status_update['Insurance_BIN']
            insurance_pcn = status_update['Insurance_PCN']
            insurance_group = status_update['Insurance_Group']
            insurance_id = status_update['Insurance_ID']
            insurance_phone = status_update['Insurance_Phone']

            # pharmacy information
            pharmacy_name = status_update['Pharmacy_Name']
            added_hub_patient_id = status_update['Added_Hub_Patient_ID']
            benefit_converted = status_update['Benefit_Converted']

            # the date action recorded must always be present and formatted, fail record if not present
            try:
                date_action_recorded = datetime.strptime(status_update['Date_Action_Recorded'], '%m/%d/%Y %H:%M:%S')
            except ValueError:
                errored_updates.append(status_update)
                continue
                

            ncpdp = status_update['NCPDP']

            # coverage submissions
            pa_fe_submitted = status_update['PA_FE_Submitted']
            pa_fe_submitted_date = status_update['PA_FE_Submitted_Date']
            pa_fe_status = status_update['PA_FE_Status']
            pa_fe_denial_reason = status_update['PA_FE_Denial_Reason']
            appeal_submitted = status_update['Appeal_Submitted']
            appeal_submitted_date = status_update['Appeal_Submitted_Date']
            appeal_status = status_update['Appeal_Status']
            appeal_denial_reason = status_update['Appeal_Denial_Reason']
            me = status_update['ME']
            me_submitted_date = status_update['ME_Submitted_Date']
            me_status = status_update['ME_Status']
            me_denial_reason = status_update['ME_Denial_Reason']
            pa_na = status_update['PA_NA']
            pa_na_submitted_date = status_update['PA_NA_Submitted_Date']

            # on label verification
            on_label = bool(status_update['ON_Label'])

            # transfer field
            mandatory_transfer = bool(status_update['Transfer'])
            
            # copay details
            copay_group_number = status_update['Group_Number']
            copay_bin = status_update['IQVIA_BIN']
            copay_pcn = status_update['IQVIA_PCN']


            new_status_update = {
                'brand_program': brand_program,
                'hub_patient_id': hub_patient_id,
                'savings_card_id': savings_card_id,
                'npi_dea': npi_dea,
                'hcp_first_name': hcp_first_name,
                'hcp_last_name': hcp_last_name,
                'hcp_address_1': hcp_address1,
                'hcp_address_2': hcp_address2,
                'hcp_city': hcp_city,
                'hcp_state': hcp_state,
                'hcp_zip': hcp_zip,
                'hcp_phone': hcp_phone,
                'payer_name': payer_name,
                'plan_name': plan_name,
                'insurance_bin': insurance_bin,
                'insurance_pcn': insurance_pcn,
                'insurance_group': insurance_group,
                'insurance_id': insurance_id,
                'insurance_phone': insurance_phone,
                'pharmacy_name': pharmacy_name,
                'added_hub_patient_id': added_hub_patient_id,
                'benefit_converted': benefit_converted,
                'date_action_recorded': date_action_recorded,
                'ncpdp': ncpdp,
                'pa_fe_submitted': pa_fe_submitted,
                'pa_fe_status': pa_fe_status,
                'pa_fe_denial_reason': pa_fe_denial_reason,
                'appeal_submitted': appeal_submitted,
                'appeal_status': appeal_status,
                'appeal_denial_reason': appeal_denial_reason,
                'medical_exception': me,
                'me_status': me_status,
                'me_denial_reason': me_denial_reason,
                'prior_authorization_na': pa_na,
                'on_label': on_label,
                'transfer': mandatory_transfer,
                'group_number': copay_group_number,
                'iqvia_bin': copay_bin,
                'iqvia_pcn': copay_pcn
            }

            # format date fields if they are populated in the status update and add into the struct
            if pa_fe_submitted_date != '':
                pa_fe_submitted_date = datetime.strptime(pa_fe_submitted_date, '%m/%d/%Y %H:%M:%S')
                new_status_update['pa_fe_submitted_date'] = pa_fe_submitted_date
            if appeal_submitted_date != '':
                appeal_submitted_date = datetime.strptime(appeal_submitted_date, '%m/%d/%Y %H:%M:%S')
                new_status_update['appeal_submitted_date'] = appeal_submitted_date
            if me_submitted_date != '':
                me_submitted_date = datetime.strptime(me_submitted_date, '%m/%d/%Y %H:%M:%S')
                new_status_update['me_submitted_date'] = me_submitted_date
            if pa_na_submitted_date != '':
                pa_na_submitted_date = datetime.strptime(pa_na_submitted_date, '%m/%d/%Y %H:%M:%S')
                new_status_update['pa_na_submitted_date'] = pa_na_submitted_date
            
            # attempt to create the record in PCP
            try:
                new_sf_record = models.SPStautsUpdate(**new_status_update)
                new_sf_record.save()
                new_updates.append(new_status_update)
            except:
                errored_updates.append(status_update)
        
        except KeyError as error:
            errored_updates.append(status_update)
    
    # return all of the successful records and all of the non successful records
    return [new_updates, errored_updates]


# -------------------------------------------------------------------------------------------------------------------- #
# scripts in the django format require a 'run' similar to a 'main'
# -------------------------------------------------------------------------------------------------------------------- #

def run():
    status_updates = load_sp_pipe_file('scripts\iqvia_data\sp_portal_files\portal_test_file')
    records = create_records(status_updates)
    print("new updates:", len(records[0]), "\nerrors:", len(records[1]))
    input('press enter to see error records...')
    for record in records[1]:
        print(record['Hub_Patient_ID'], record['Savings_Card_ID'])

