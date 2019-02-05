#!/bin/sh
BASE=.tox/py36-dj21-pylint
source $BASE/bin/activate
DJANGO_SETTINGS_MODULE=salesforce.testrunner.settings $BASE/bin/pylint salesforce $@
