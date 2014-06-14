#!/bin/bash
python manage.py inspectdb --database=salesforce >tests/inspectdb/models.py && \
python manage.py validate --settings=tests.inspectdb.settings && \
python tests/inspectdb/slow_test.py
