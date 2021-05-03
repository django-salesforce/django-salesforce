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
from salesforce.testrunner.example import models


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

    for status_update in status_updates:
        """ load key, value pair into salesforce """
        # general program data
        print(status_update['Brand_Program'])
        print(status_update['Hub_Patient_ID'])
        print(status_update['Savings_Card_ID'])
        
        # physician information
        print(status_update['NPI_DEA'])
        print(status_update['HCP_First_Name'])
        print(status_update['HCP_Last_Name'])
        print(status_update['HCP_Address1'])
        print(status_update['HCP_Address2'])
        print(status_update['HCP_City'])
        print(status_update['HCP_State'])
        print(status_update['HCP_Zip'])
        print(status_update['HCP_Phone'])

        # insurance information
        print(status_update['Payer_Name'])
        print(status_update['Plan_Name'])
        print(status_update['Insurance_BIN'])
        print(status_update['Insurance_PCN'])
        print(status_update['Insurance_Group'])

        print(status_update['Insurance_ID'])
        print(status_update['Insurance_Phone'])

        # pharmacy information
        print(status_update['Pharmacy_Name'])
        # this field is in the FIA, but is throwing an error... print(
        # status_update['Added_HUB_Patient_ID']
        
        # coverage submissions
        print(status_update['PA_FE_Submitted'])
        print(status_update['PA_FE_Submitted_Date'])
        print(status_update['PA_FE_Status'])
        # throws an error... 
        # status_update['PA_FE_Denial_Reason']
        print(status_update['Appeal_Submitted'])
        print(status_update['Appeal_Status'])
        print(status_update['Appeal_Denial_Reason'])
        print(status_update['ME'])
        print(status_update['ME_Submitted_Date'])
        print(status_update['ME_Status'])
        print(status_update['ME_Denial_Reason'])
        print(status_update['PA_NA'])

        # on label verification
        print(status_update['ON_Label'])

        # transfer field
        print(status_update['Transfer'])
        
        # copay details
        print(status_update['Group_Number'])
        print(status_update['IQVIA_BIN'])
        print(status_update['IQVIA_PCN'])
        
    
        # stop gap to next update
        input("\npress enter to see next update...")
        print("")

        # models.SPStatusUpdate.objects.create()


# -------------------------------------------------------------------------------------------------------------------- #
# scripts in the django format require a 'run' similar to a 'main'
# -------------------------------------------------------------------------------------------------------------------- #

def run():
    status_updates = load_sp_pipe_file('scripts\iqvia_data\sp_portal_files\production_4_30_2021')
    create_records(status_updates)

