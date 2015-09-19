#!/bin/sh
TEST_BASE=tests.
python manage.py test --settings=tests.test_dynamic_auth.settings ${TEST_BASE}test_dynamic_auth
