#!/bin/sh
TEST_BASE=tests.
python manage.py test --settings=tests.test_mixin.settings ${TEST_BASE}test_mixin
