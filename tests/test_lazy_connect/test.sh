#!/bin/sh
TEST_BASE=tests.
python manage.py test --settings=tests.test_lazy_connect.settings ${TEST_BASE}test_lazy_connect
