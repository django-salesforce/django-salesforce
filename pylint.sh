#!/bin/sh
BASE=.tox/pylint-dj32-py38
source $BASE/bin/activate
DJANGO_SETTINGS_MODULE=salesforce.testrunner.settings $BASE/bin/pylint salesforce $@
