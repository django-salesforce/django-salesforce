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
    """ function to actually create the records in the pcp... """
    for status_update in status_updates[0]:
        print(status_update)
        models.SPStatusUpdate.objects.create()


# -------------------------------------------------------------------------------------------------------------------- #
# scripts in the django format require a 'run' similar to a 'main'
# -------------------------------------------------------------------------------------------------------------------- #

def run():
    test_updates = load_sp_pipe_file('scripts\iqvia_data\sp_portal_files\portal_test_file')
    create_records(test_updates)
