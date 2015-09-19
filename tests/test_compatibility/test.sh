#!/bin/sh
TEST_BASE=tests.
python manage.py test --settings=tests.test_compatibility.settings ${TEST_BASE}test_compatibility
